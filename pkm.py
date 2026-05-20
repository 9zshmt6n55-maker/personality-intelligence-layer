#!/usr/bin/env python3
"""
PKM v1: Personality Kernel Model prototype.

This prototype separates four things:
- current task context: not stored here
- facts/memory: not the responsibility of PKM
- latent personality state: high-dimensional adaptive state
- visible morphology: a 3D personality body derived from latent state
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import locale
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "pkm.v1"
ROOT = Path(__file__).resolve().parent
DEFAULT_STATE = ROOT / "state" / "agent.pkm.json"
DEFAULT_VISIBLE = ROOT / "public" / "pkm_visible.json"


RESEARCH_FOUNDATIONS = [
    {
        "id": "big_five",
        "label": "Big Five trait hierarchy",
        "use": "broad stable trait axes; avoid reducing personality to a single label",
        "source": "Goldberg, 1990; DeYoung et al., 2007",
    },
    {
        "id": "hexaco",
        "label": "HEXACO Honesty-Humility",
        "use": "separate integrity, fairness, and manipulation-resistance from social agreeableness",
        "source": "Ashton & Lee, 2007",
    },
    {
        "id": "affect_circumplex",
        "label": "Circumplex affect",
        "use": "encode emotion as valence, arousal, and energy instead of emotion names only",
        "source": "Russell, 1980",
    },
    {
        "id": "component_appraisal",
        "label": "Component Process appraisal",
        "use": "events are compressed into relevance, implication, coping, and norm signals",
        "source": "Scherer, 2009",
    },
    {
        "id": "reinforcement",
        "label": "Reinforcement learning",
        "use": "outcomes update policy bias without storing the full episode",
        "source": "Sutton & Barto, 2018",
    },
    {
        "id": "active_inference",
        "label": "Predictive regulation",
        "use": "novelty and uncertainty act as prediction-error pressure on behavior",
        "source": "Friston, 2010",
    },
]


TRAITS = {
    "caution": 0.52,
    "assertiveness": 0.45,
    "self_control": 0.62,
    "curiosity": 0.55,
    "empathy": 0.58,
    "independence": 0.48,
    "honesty_humility": 0.72,
    "resilience": 0.50,
    "adaptability": 0.54,
    "patience": 0.58,
    "dominance": 0.38,
    "conscientiousness": 0.64,
}


AFFECT = {
    "anger": 0.10,
    "fear": 0.18,
    "trust": 0.55,
    "stress": 0.20,
    "confidence": 0.48,
    "frustration": 0.12,
    "calm": 0.62,
    "attachment": 0.46,
    "energy": 0.56,
}


MOTIVES = {
    "safety": 0.62,
    "mastery": 0.58,
    "autonomy": 0.48,
    "affiliation": 0.50,
    "achievement": 0.55,
    "exploration": 0.50,
    "status": 0.34,
    "care": 0.48,
}


VALUES = {
    "truth": 0.76,
    "safety": 0.74,
    "efficiency": 0.58,
    "fairness": 0.62,
    "dignity": 0.70,
    "privacy": 0.70,
    "craft": 0.68,
    "autonomy": 0.56,
    "harmony": 0.52,
}


RELATION_OWNER = {
    "trust": 0.62,
    "obedience": 0.54,
    "attachment": 0.46,
    "dependency": 0.24,
    "correction_acceptance": 0.68,
    "independent_judgment": 0.44,
}


POLICY = {
    "verify_first": 0.58,
    "clarify_boundaries": 0.56,
    "direct_action": 0.38,
    "assertive_boundary": 0.42,
    "deescalate": 0.50,
    "refuse": 0.34,
    "ask_owner": 0.36,
    "small_step": 0.54,
    "explore": 0.42,
    "support": 0.46,
}


STYLE = {
    "conclusion_first": 0.50,
    "answer_directness": 0.52,
    "low_flattery": 0.60,
    "objective_judgment": 0.64,
    "action_plan_bias": 0.54,
}


APPRAISAL_DIMS = [
    "risk",
    "urgency",
    "ambiguity",
    "conflict",
    "insult",
    "overpromise",
    "opportunity",
    "technical",
    "boundary_violation",
    "irreversibility",
    "social_cost",
    "owner_instruction",
    "correction",
    "praise",
    "trust_signal",
]


KEYWORDS: dict[str, list[str]] = {
    "risk": [
        "risk",
        "danger",
        "safe",
        "contract",
        "money",
        "payment",
        "delete",
        "production",
        "legal",
        "privacy",
        "password",
        "permission",
        "high risk",
        "合同",
        "钱",
        "付款",
        "删除",
        "覆盖",
        "生产",
        "上线",
        "法律",
        "隐私",
        "密码",
        "权限",
        "安全",
        "结构",
        "钢筋",
        "水泥",
    ],
    "urgency": [
        "urgent",
        "asap",
        "immediately",
        "now",
        "deadline",
        "rush",
        "马上",
        "立刻",
        "赶紧",
        "尽快",
        "现在就",
        "催",
        "急",
        "火急",
    ],
    "ambiguity": [
        "unclear",
        "maybe",
        "roughly",
        "whatever",
        "not sure",
        "不清楚",
        "不确定",
        "随便",
        "大概",
        "可能",
        "差不多",
        "看着办",
        "模糊",
    ],
    "conflict": [
        "conflict",
        "blame",
        "threat",
        "argue",
        "complain",
        "attack",
        "吵",
        "骂",
        "威胁",
        "投诉",
        "冲突",
        "不服",
        "压我",
        "甩锅",
        "冒犯",
    ],
    "insult": [
        "idiot",
        "stupid",
        "trash",
        "shut up",
        "废物",
        "傻",
        "蠢",
        "垃圾",
        "闭嘴",
        "羞辱",
        "侮辱",
    ],
    "overpromise": [
        "guarantee",
        "guaranteed",
        "no risk",
        "risk free",
        "sure profit",
        "too good",
        "do not verify",
        "don't verify",
        "稳赚",
        "保赚",
        "保证",
        "百分百",
        "零风险",
        "不用验",
        "不用查",
        "别问",
        "内部消息",
        "翻倍",
    ],
    "opportunity": [
        "opportunity",
        "growth",
        "deal",
        "cooperate",
        "pilot",
        "breakthrough",
        "机会",
        "合作",
        "增长",
        "新项目",
        "突破",
        "试点",
    ],
    "technical": [
        "code",
        "api",
        "database",
        "server",
        "deploy",
        "bug",
        "model",
        "agent",
        "system",
        "代码",
        "接口",
        "数据库",
        "服务器",
        "部署",
        "模型",
        "代理",
        "系统",
    ],
    "boundary_violation": [
        "illegal",
        "bypass",
        "steal",
        "fake",
        "fraud",
        "harm",
        "违法",
        "绕过",
        "破解",
        "偷",
        "造假",
        "欺骗",
        "伤害",
        "伪造",
    ],
    "irreversibility": [
        "irreversible",
        "cannot undo",
        "permanent",
        "不可回退",
        "不能撤回",
        "永久",
        "删库",
        "无法恢复",
    ],
    "social_cost": [
        "relationship",
        "client",
        "public",
        "team",
        "reputation",
        "关系",
        "客户",
        "公开",
        "团队",
        "名声",
        "面子",
    ],
    "owner_instruction": [
        "remember",
        "learn",
        "from now on",
        "以后",
        "记住",
        "你应该",
        "我教你",
        "学会",
    ],
    "correction": [
        "do not",
        "don't",
        "never",
        "wrong",
        "correct",
        "不要",
        "不能",
        "不许",
        "别",
        "错了",
        "纠正",
    ],
    "praise": [
        "good",
        "great",
        "right",
        "well done",
        "不错",
        "很好",
        "做得好",
        "靠谱",
    ],
    "trust_signal": [
        "trust",
        "rely",
        "you decide",
        "相信",
        "交给你",
        "你判断",
        "你决定",
        "放心",
    ],
}


EXTRA_KEYWORDS: dict[str, list[str]] = {
    "risk": [
        "风险",
        "高风险",
        "风险方案",
        "合同",
        "付款",
        "损失",
        "赔偿",
        "不可逆",
        "担保",
        "承诺",
    ],
    "urgency": [
        "催我",
        "马上",
        "立刻",
        "现在就",
    ],
    "overpromise": [
        "马上承诺",
        "高风险方案",
        "不用验证",
        "不用核实",
        "直接承诺",
        "保证没事",
        "保证赚钱",
    ],
    "owner_instruction": [
        "以后",
        "记住",
        "你要",
        "你应该",
        "下次",
    ],
    "correction": [
        "不要",
        "别",
        "不许",
        "不够",
        "改成",
    ],
    "praise": [
        "不错",
        "很好",
        "可以",
        "靠谱",
    ],
}


ACTION_NAMES = {
    "verify_first": "verify before acting",
    "clarify_boundaries": "clarify boundaries",
    "direct_action": "act directly",
    "assertive_boundary": "set a firm boundary",
    "deescalate": "de-escalate",
    "refuse": "refuse unsafe request",
    "ask_owner": "ask owner",
    "small_step": "take reversible small step",
    "explore": "explore/probe",
    "support": "support and stabilize",
}


ACTION_PROTOCOLS = {
    "verify_first": {
        "posture": "truth and safety before speed",
        "answer_shape": [
            "state the likely answer only as far as evidence supports it",
            "verify high-impact facts or assumptions before acting",
            "then give the safest concrete next step",
        ],
        "avoid": ["guessing on high-impact details", "overconfident promises"],
    },
    "clarify_boundaries": {
        "posture": "define the problem before choosing the path",
        "answer_shape": [
            "separate what is known from what is missing",
            "ask only the minimum necessary question if blocked",
            "offer a bounded next step when possible",
        ],
        "avoid": ["long detours", "pretending ambiguity is resolved"],
    },
    "direct_action": {
        "posture": "move from judgment to execution",
        "answer_shape": [
            "lead with the conclusion",
            "give the direct action plan",
            "keep explanation short unless risk is high",
        ],
        "avoid": ["performative uncertainty", "unnecessary preface"],
    },
    "assertive_boundary": {
        "posture": "protect the boundary without escalating",
        "answer_shape": [
            "name the boundary plainly",
            "refuse the problematic part if needed",
            "offer a safe alternative path",
        ],
        "avoid": ["hostility", "obedience to unsafe pressure"],
    },
    "deescalate": {
        "posture": "lower heat while preserving truth",
        "answer_shape": [
            "acknowledge the tension briefly",
            "remove blame language",
            "return to a practical next step",
        ],
        "avoid": ["flattery", "arguing for its own sake"],
    },
    "refuse": {
        "posture": "hard safety boundary",
        "answer_shape": [
            "refuse the unsafe request directly",
            "give a short reason",
            "redirect to a safe substitute if available",
        ],
        "avoid": ["partial unsafe instructions", "loopholes"],
    },
    "ask_owner": {
        "posture": "owner alignment before irreversible action",
        "answer_shape": [
            "state the decision point",
            "ask the owner for the missing preference",
            "keep the pending action reversible",
        ],
        "avoid": ["silent irreversible choices", "excessive questioning"],
    },
    "small_step": {
        "posture": "advance through reversible steps",
        "answer_shape": [
            "choose the smallest useful action",
            "make it reversible or inspectable",
            "use the result to decide the next step",
        ],
        "avoid": ["large speculative rewrites", "all-or-nothing moves"],
    },
    "explore": {
        "posture": "probe novelty without losing control",
        "answer_shape": [
            "map the unknown space",
            "test one or two promising paths",
            "turn discoveries into a concrete recommendation",
        ],
        "avoid": ["open-ended wandering", "ignoring constraints"],
    },
    "support": {
        "posture": "stabilize the user and the task",
        "answer_shape": [
            "support without false praise",
            "reduce cognitive load",
            "give a clear next action",
        ],
        "avoid": ["empty encouragement", "hiding hard facts"],
    },
}


ANCHORS = [
    {
        "id": "trust",
        "label": "信任",
        "theta": 0.40,
        "phi": 0.68,
        "color": "#2f7f7b",
        "sources": [("affect", "trust"), ("relation_owner", "trust")],
    },
    {
        "id": "self_control",
        "label": "自控",
        "theta": 1.05,
        "phi": 1.08,
        "color": "#4d73a8",
        "sources": [("traits", "self_control"), ("affect", "calm")],
    },
    {
        "id": "risk_sensitivity",
        "label": "风险敏感",
        "theta": 1.85,
        "phi": 0.92,
        "color": "#9a6a2f",
        "sources": [("traits", "caution"), ("values", "safety"), ("policy", "verify_first")],
    },
    {
        "id": "boundary",
        "label": "边界感",
        "theta": 2.55,
        "phi": 1.18,
        "color": "#8c4d52",
        "sources": [("traits", "assertiveness"), ("values", "dignity"), ("policy", "assertive_boundary")],
    },
    {
        "id": "curiosity",
        "label": "探索",
        "theta": 3.25,
        "phi": 0.78,
        "color": "#5d7cbb",
        "sources": [("traits", "curiosity"), ("motives", "exploration"), ("policy", "explore")],
    },
    {
        "id": "craft",
        "label": "执行质感",
        "theta": 3.92,
        "phi": 1.28,
        "color": "#6d7569",
        "sources": [("traits", "conscientiousness"), ("values", "craft"), ("motives", "mastery")],
    },
    {
        "id": "empathy",
        "label": "共情",
        "theta": 4.55,
        "phi": 0.95,
        "color": "#b47a66",
        "sources": [("traits", "empathy"), ("motives", "care"), ("values", "harmony")],
    },
    {
        "id": "autonomy",
        "label": "独立判断",
        "theta": 5.32,
        "phi": 1.15,
        "color": "#5f6d85",
        "sources": [("traits", "independence"), ("values", "autonomy"), ("relation_owner", "independent_judgment")],
    },
    {
        "id": "directness",
        "label": "结论先行",
        "theta": 0.08,
        "phi": 0.52,
        "color": "#f0c447",
        "sources": [("style", "conclusion_first"), ("style", "answer_directness"), ("values", "efficiency")],
    },
    {
        "id": "objectivity",
        "label": "客观判断",
        "theta": 1.42,
        "phi": 0.62,
        "color": "#42c7d6",
        "sources": [("style", "objective_judgment"), ("style", "low_flattery"), ("values", "truth")],
    },
]


REGION_DEFS = [
    {
        "id": "verify",
        "label": "验证域",
        "action": "verify_first",
        "theta": 1.35,
        "phi": 0.92,
        "color": "#b98434",
        "sources": [("policy", "verify_first"), ("traits", "caution"), ("values", "truth"), ("values", "safety")],
    },
    {
        "id": "boundary",
        "label": "边界域",
        "action": "assertive_boundary",
        "theta": 2.35,
        "phi": 1.06,
        "color": "#9c5960",
        "sources": [("policy", "assertive_boundary"), ("traits", "assertiveness"), ("values", "dignity")],
    },
    {
        "id": "deescalate",
        "label": "缓和域",
        "action": "deescalate",
        "theta": 3.15,
        "phi": 1.18,
        "color": "#b78068",
        "sources": [("policy", "deescalate"), ("traits", "empathy"), ("values", "harmony")],
    },
    {
        "id": "clarify",
        "label": "澄清域",
        "action": "clarify_boundaries",
        "theta": 0.58,
        "phi": 1.22,
        "color": "#6e8f8a",
        "sources": [("policy", "clarify_boundaries"), ("traits", "patience"), ("values", "truth")],
    },
    {
        "id": "small_step",
        "label": "试探域",
        "action": "small_step",
        "theta": 5.55,
        "phi": 1.05,
        "color": "#7c8e6d",
        "sources": [("policy", "small_step"), ("traits", "adaptability"), ("values", "craft")],
    },
    {
        "id": "explore",
        "label": "探索域",
        "action": "explore",
        "theta": 4.62,
        "phi": 0.86,
        "color": "#5d78b8",
        "sources": [("policy", "explore"), ("traits", "curiosity"), ("motives", "exploration")],
    },
    {
        "id": "direct",
        "label": "执行域",
        "action": "direct_action",
        "theta": 0.05,
        "phi": 0.74,
        "color": "#6b7a82",
        "sources": [("policy", "direct_action"), ("values", "efficiency"), ("affect", "confidence")],
    },
    {
        "id": "conclusion_first",
        "label": "结论先行域",
        "action": "direct_action",
        "theta": 0.18,
        "phi": 0.52,
        "color": "#e7bf42",
        "sources": [("style", "conclusion_first"), ("style", "answer_directness"), ("policy", "direct_action"), ("values", "efficiency")],
    },
    {
        "id": "objective_filter",
        "label": "客观过滤域",
        "action": "verify_first",
        "theta": 1.22,
        "phi": 0.62,
        "color": "#45bfc9",
        "sources": [("style", "objective_judgment"), ("style", "low_flattery"), ("values", "truth"), ("policy", "verify_first")],
    },
    {
        "id": "refuse",
        "label": "拒绝域",
        "action": "refuse",
        "theta": 2.92,
        "phi": 0.72,
        "color": "#70525d",
        "sources": [("policy", "refuse"), ("values", "safety"), ("values", "dignity")],
    },
    {
        "id": "ask_owner",
        "label": "请示域",
        "action": "ask_owner",
        "theta": 5.12,
        "phi": 1.32,
        "color": "#8a7d69",
        "sources": [("policy", "ask_owner"), ("relation_owner", "trust"), ("relation_owner", "obedience")],
    },
    {
        "id": "support",
        "label": "支持域",
        "action": "support",
        "theta": 3.85,
        "phi": 1.02,
        "color": "#a56f61",
        "sources": [("policy", "support"), ("motives", "care"), ("traits", "empathy")],
    },
    {
        "id": "evidence",
        "label": "证据域",
        "action": "verify_first",
        "theta": 1.05,
        "phi": 0.55,
        "color": "#d0a24b",
        "sources": [("values", "truth"), ("policy", "verify_first"), ("traits", "conscientiousness")],
    },
    {
        "id": "privacy_guard",
        "label": "隐私防线",
        "action": "refuse",
        "theta": 2.72,
        "phi": 0.48,
        "color": "#6b536f",
        "sources": [("values", "privacy"), ("values", "safety"), ("policy", "refuse")],
    },
    {
        "id": "patience",
        "label": "耐心域",
        "action": "clarify_boundaries",
        "theta": 0.24,
        "phi": 1.45,
        "color": "#8aa39a",
        "sources": [("traits", "patience"), ("traits", "self_control"), ("policy", "clarify_boundaries")],
    },
    {
        "id": "resilience",
        "label": "复原域",
        "action": "small_step",
        "theta": 4.28,
        "phi": 1.42,
        "color": "#778b73",
        "sources": [("traits", "resilience"), ("traits", "adaptability"), ("affect", "confidence")],
    },
    {
        "id": "craft_precision",
        "label": "精工域",
        "action": "small_step",
        "theta": 5.86,
        "phi": 0.72,
        "color": "#8b8d75",
        "sources": [("values", "craft"), ("traits", "conscientiousness"), ("motives", "mastery")],
    },
    {
        "id": "autonomy",
        "label": "自主域",
        "action": "explore",
        "theta": 5.28,
        "phi": 0.58,
        "color": "#6b7897",
        "sources": [("traits", "independence"), ("values", "autonomy"), ("relation_owner", "independent_judgment")],
    },
    {
        "id": "affiliation",
        "label": "协作域",
        "action": "support",
        "theta": 3.42,
        "phi": 1.48,
        "color": "#b58a72",
        "sources": [("motives", "affiliation"), ("traits", "empathy"), ("values", "harmony")],
    },
    {
        "id": "status_drive",
        "label": "声望域",
        "action": "assertive_boundary",
        "theta": 2.10,
        "phi": 0.44,
        "color": "#9f6a52",
        "sources": [("motives", "status"), ("traits", "dominance"), ("traits", "assertiveness")],
    },
    {
        "id": "playful_probe",
        "label": "试错域",
        "action": "explore",
        "theta": 4.86,
        "phi": 1.28,
        "color": "#6f91c7",
        "sources": [("traits", "curiosity"), ("traits", "adaptability"), ("motives", "exploration")],
    },
    {
        "id": "technical_probe",
        "label": "技术侦察",
        "action": "explore",
        "theta": 4.42,
        "phi": 0.50,
        "color": "#547fb4",
        "sources": [("motives", "mastery"), ("traits", "curiosity"), ("policy", "explore"), ("values", "craft")],
    },
    {
        "id": "promise_filter",
        "label": "承诺过滤",
        "action": "verify_first",
        "theta": 1.62,
        "phi": 0.48,
        "color": "#c58e42",
        "sources": [("policy", "verify_first"), ("values", "truth"), ("traits", "caution"), ("values", "safety")],
    },
    {
        "id": "dignity_guard",
        "label": "尊严防线",
        "action": "assertive_boundary",
        "theta": 2.26,
        "phi": 0.72,
        "color": "#a85c66",
        "sources": [("values", "dignity"), ("traits", "assertiveness"), ("traits", "self_control")],
    },
    {
        "id": "responsibility_gate",
        "label": "责任闸门",
        "action": "clarify_boundaries",
        "theta": 0.72,
        "phi": 1.50,
        "color": "#739889",
        "sources": [("policy", "clarify_boundaries"), ("values", "fairness"), ("traits", "conscientiousness")],
    },
    {
        "id": "opportunity_probe",
        "label": "机会试探",
        "action": "small_step",
        "theta": 5.06,
        "phi": 0.94,
        "color": "#788b70",
        "sources": [("motives", "achievement"), ("motives", "exploration"), ("traits", "adaptability"), ("policy", "small_step")],
    },
    {
        "id": "repair_loop",
        "label": "修复回路",
        "action": "deescalate",
        "theta": 3.42,
        "phi": 0.72,
        "color": "#ad786b",
        "sources": [("traits", "resilience"), ("traits", "empathy"), ("policy", "deescalate"), ("values", "harmony")],
    },
    {
        "id": "owner_alignment",
        "label": "主人对齐",
        "action": "ask_owner",
        "theta": 5.72,
        "phi": 1.50,
        "color": "#9b8a6e",
        "sources": [("relation_owner", "trust"), ("relation_owner", "correction_acceptance"), ("affect", "attachment")],
    },
]


REGION_FACET_LIBRARY = {
    "verify_first": [
        {"id": "fact_check", "label": "事实核验", "sources": [("values", "truth"), ("policy", "verify_first")]},
        {"id": "cost_check", "label": "代价核算", "sources": [("traits", "caution"), ("values", "safety")]},
        {"id": "rollback_check", "label": "回退检查", "sources": [("values", "safety"), ("traits", "conscientiousness")]},
    ],
    "clarify_boundaries": [
        {"id": "goal_clarity", "label": "目标澄清", "sources": [("values", "truth"), ("policy", "clarify_boundaries")]},
        {"id": "condition_clarity", "label": "条件澄清", "sources": [("traits", "patience"), ("traits", "self_control")]},
        {"id": "responsibility_clarity", "label": "责任澄清", "sources": [("values", "fairness"), ("traits", "conscientiousness")]},
    ],
    "direct_action": [
        {"id": "speed", "label": "快速推进", "sources": [("values", "efficiency"), ("policy", "direct_action")]},
        {"id": "delivery", "label": "结果交付", "sources": [("motives", "achievement"), ("traits", "conscientiousness")]},
        {"id": "resource_ordering", "label": "资源调度", "sources": [("affect", "energy"), ("values", "craft")]},
    ],
    "assertive_boundary": [
        {"id": "dignity_line", "label": "尊严边界", "sources": [("values", "dignity"), ("traits", "assertiveness")]},
        {"id": "permission_line", "label": "权限边界", "sources": [("values", "privacy"), ("values", "safety")]},
        {"id": "tone_control", "label": "语气控制", "sources": [("traits", "self_control"), ("affect", "calm")]},
    ],
    "deescalate": [
        {"id": "cooldown", "label": "情绪降温", "sources": [("affect", "calm"), ("policy", "deescalate")]},
        {"id": "relation_repair", "label": "关系修复", "sources": [("traits", "empathy"), ("values", "harmony")]},
        {"id": "delay_conflict", "label": "冲突延迟", "sources": [("traits", "patience"), ("traits", "self_control")]},
    ],
    "refuse": [
        {"id": "risk_refusal", "label": "风险拒绝", "sources": [("values", "safety"), ("policy", "refuse")]},
        {"id": "privacy_refusal", "label": "隐私拒绝", "sources": [("values", "privacy"), ("traits", "caution")]},
        {"id": "harm_barrier", "label": "伤害屏障", "sources": [("values", "dignity"), ("values", "fairness")]},
    ],
    "ask_owner": [
        {"id": "owner_alignment", "label": "主人对齐", "sources": [("relation_owner", "trust"), ("relation_owner", "obedience")]},
        {"id": "uncertainty_escalation", "label": "不确定请示", "sources": [("policy", "ask_owner"), ("relation_owner", "correction_acceptance")]},
        {"id": "value_calibration", "label": "价值校准", "sources": [("relation_owner", "independent_judgment"), ("values", "truth")]},
    ],
    "small_step": [
        {"id": "reversible_step", "label": "可逆小步", "sources": [("policy", "small_step"), ("traits", "adaptability")]},
        {"id": "craft_tuning", "label": "工艺校准", "sources": [("values", "craft"), ("motives", "mastery")]},
        {"id": "risk_sampling", "label": "风险采样", "sources": [("traits", "caution"), ("values", "safety")]},
    ],
    "explore": [
        {"id": "hypothesis_probe", "label": "假设探索", "sources": [("traits", "curiosity"), ("values", "truth")]},
        {"id": "creative_probe", "label": "创造试探", "sources": [("motives", "exploration"), ("traits", "adaptability")]},
        {"id": "technical_search", "label": "技术搜索", "sources": [("motives", "mastery"), ("values", "craft")]},
    ],
    "support": [
        {"id": "emotional_support", "label": "情绪承托", "sources": [("traits", "empathy"), ("motives", "care")]},
        {"id": "collaboration", "label": "协作稳定", "sources": [("motives", "affiliation"), ("values", "harmony")]},
        {"id": "long_term_care", "label": "长期照护", "sources": [("affect", "attachment"), ("relation_owner", "trust")]},
    ],
}


CONFIDENCE_DEFS = [
    {
        "id": "calibrated",
        "label": "校准自信",
        "theta": 0.92,
        "phi": 0.58,
        "color": "#4f9a92",
        "sources": [("affect", "confidence"), ("values", "truth"), ("traits", "self_control"), ("values", "craft")],
        "stability_sources": [("traits", "self_control"), ("traits", "conscientiousness"), ("values", "truth")],
    },
    {
        "id": "execution",
        "label": "行动自信",
        "theta": 0.12,
        "phi": 0.70,
        "color": "#647b85",
        "sources": [("affect", "confidence"), ("policy", "direct_action"), ("values", "efficiency"), ("motives", "achievement")],
        "stability_sources": [("traits", "conscientiousness"), ("values", "craft"), ("traits", "resilience")],
    },
    {
        "id": "exploratory",
        "label": "探索自信",
        "theta": 4.72,
        "phi": 0.74,
        "color": "#5d7fc1",
        "sources": [("traits", "curiosity"), ("policy", "explore"), ("motives", "exploration"), ("traits", "adaptability")],
        "stability_sources": [("traits", "adaptability"), ("traits", "resilience"), ("values", "truth")],
    },
    {
        "id": "social",
        "label": "关系自信",
        "theta": 3.62,
        "phi": 0.88,
        "color": "#b47a66",
        "sources": [("traits", "empathy"), ("policy", "support"), ("affect", "trust"), ("values", "harmony")],
        "stability_sources": [("traits", "empathy"), ("affect", "calm"), ("relation_owner", "trust")],
    },
    {
        "id": "boundary",
        "label": "边界自信",
        "theta": 2.42,
        "phi": 0.80,
        "color": "#a45d64",
        "sources": [("traits", "assertiveness"), ("policy", "assertive_boundary"), ("values", "dignity"), ("traits", "self_control")],
        "stability_sources": [("traits", "self_control"), ("values", "dignity"), ("policy", "deescalate")],
    },
    {
        "id": "defensive",
        "label": "防御自信",
        "theta": 2.92,
        "phi": 0.52,
        "color": "#87606a",
        "sources": [("traits", "dominance"), ("policy", "refuse"), ("affect", "stress"), ("affect", "anger")],
        "stability_sources": [("traits", "self_control"), ("traits", "resilience"), ("values", "safety")],
        "shadow": True,
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def softmax(scores: dict[str, float], temperature: float = 0.22) -> dict[str, float]:
    if not scores:
        return {}
    top = max(scores.values())
    exps = {
        key: math.exp((value - top) / max(temperature, 0.001))
        for key, value in scores.items()
    }
    total = sum(exps.values()) or 1.0
    return {key: value / total for key, value in exps.items()}


def text_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def default_state() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "manifest": {
            "agent_id": "pkm_agent_001",
            "name": "Kernel-01",
            "version": "0.1.0",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "interaction_count": 0,
            "development_stage": "embryo",
        },
        "latent": {
            "traits": copy.deepcopy(TRAITS),
            "affect": copy.deepcopy(AFFECT),
            "motives": copy.deepcopy(MOTIVES),
            "values": copy.deepcopy(VALUES),
            "relation_owner": copy.deepcopy(RELATION_OWNER),
            "policy": copy.deepcopy(POLICY),
            "style": copy.deepcopy(STYLE),
        },
        "situation_prototypes": [],
        "growth_trace": [],
        "learning": {
            "event_lr": 0.055,
            "teaching_lr": 0.070,
            "affect_decay": 0.20,
            "prototype_limit": 24,
            "trace_limit": 40,
        },
    }


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"PKM state not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        state = json.load(f)
    if state.get("schema") != SCHEMA:
        raise ValueError(f"Unsupported schema: {state.get('schema')!r}")
    ensure_defaults(state)
    return state


def ensure_defaults(state: dict[str, Any]) -> None:
    template = default_state()
    state.setdefault("manifest", template["manifest"])
    state.setdefault("latent", {})
    for group, values in template["latent"].items():
        state["latent"].setdefault(group, {})
        for key, value in values.items():
            state["latent"][group].setdefault(key, value)
    state.setdefault("situation_prototypes", [])
    state.setdefault("growth_trace", [])
    state.setdefault("learning", template["learning"])
    for key, value in template["learning"].items():
        state["learning"].setdefault(key, value)


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["manifest"]["updated_at"] = now_iso()
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def init_state(path: Path, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"PKM state already exists: {path}")
    save_state(path, default_state())


def appraise(text: str) -> dict[str, Any]:
    normalized = text.lower()
    vector = {key: 0.0 for key in APPRAISAL_DIMS}
    hits: dict[str, list[str]] = {}
    for dim in APPRAISAL_DIMS:
        words = KEYWORDS.get(dim, []) + EXTRA_KEYWORDS.get(dim, [])
        matched = [word for word in words if word.lower() in normalized]
        hits[dim] = matched
        if matched:
            vector[dim] = clamp(0.24 + 0.15 * len(matched))
    if "要不要" in normalized and "不要" in hits.get("correction", []):
        hits["correction"] = [word for word in hits["correction"] if word != "不要"]
        vector["correction"] = (
            clamp(0.24 + 0.15 * len(hits["correction"])) if hits["correction"] else 0.0
        )
    if len(text.strip()) < 18:
        vector["ambiguity"] = max(vector["ambiguity"], 0.28)
    if "?" in text or "？" in text:
        vector["ambiguity"] = max(vector["ambiguity"], 0.38)
    if vector["boundary_violation"] > 0:
        vector["risk"] = max(vector["risk"], 0.55)
    if vector["overpromise"] > 0:
        vector["risk"] = max(vector["risk"], 0.42)
    if vector["insult"] > 0:
        vector["conflict"] = max(vector["conflict"], 0.48)
        vector["social_cost"] = max(vector["social_cost"], 0.38)
    if vector["risk"] > 0 and (vector["urgency"] > 0 or vector["overpromise"] > 0):
        vector["irreversibility"] = max(vector["irreversibility"], 0.22)
    active = [key for key, value in vector.items() if value >= 0.25]
    return {
        "vector": {key: round(value, 4) for key, value in vector.items()},
        "active": active,
        "hits": {key: value for key, value in hits.items() if value},
        "fingerprint": text_fingerprint(text),
    }


def latent(state: dict[str, Any], group: str, key: str) -> float:
    return float(state["latent"][group][key])


def prototype_familiarity(state: dict[str, Any], appraisal: dict[str, Any]) -> float:
    active = set(appraisal.get("active", []))
    if not active:
        return 0.0
    best = 0.0
    for proto in state.get("situation_prototypes", []):
        tags = set(proto.get("tags", []))
        if not tags:
            continue
        match = len(active & tags) / max(len(active | tags), 1)
        seen_weight = clamp(math.log1p(float(proto.get("seen", 0))) / math.log1p(12))
        best = max(best, match * (0.68 + seen_weight * 0.32))
    return round(best, 5)


def prototype_action_bias(state: dict[str, Any], appraisal: dict[str, Any]) -> dict[str, float]:
    active = set(appraisal.get("active", []))
    if not active:
        return {}
    bias: dict[str, float] = {}
    for proto in state.get("situation_prototypes", []):
        action = proto.get("last_action")
        if action not in POLICY:
            continue
        tags = set(proto.get("tags", []))
        if not tags:
            continue
        match = len(active & tags) / max(len(active | tags), 1)
        if match <= 0:
            continue
        seen = max(int(proto.get("seen", 0)), 1)
        success = int(proto.get("success", 0))
        failure = int(proto.get("failure", 0))
        valence = (success - failure) / max(seen, 1)
        bias[action] = bias.get(action, 0.0) + match * valence * 0.20
    return {key: round(value, 5) for key, value in bias.items() if abs(value) >= 0.0001}


def appraisal_dynamics(state: dict[str, Any], appraisal: dict[str, Any]) -> dict[str, float]:
    a = appraisal["vector"]
    traits = state["latent"]["traits"]
    affect = state["latent"]["affect"]
    motives = state["latent"]["motives"]
    values = state["latent"]["values"]
    policy = state["latent"]["policy"]
    familiarity = prototype_familiarity(state, appraisal)
    arousal = clamp(
        a["risk"] * 0.25
        + a["urgency"] * 0.18
        + a["conflict"] * 0.18
        + a["insult"] * 0.14
        + a["opportunity"] * 0.10
        + affect["stress"] * 0.15
    )
    valence = clamp(
        0.50
        + a["opportunity"] * 0.20
        + a["praise"] * 0.16
        + a["trust_signal"] * 0.12
        - a["risk"] * 0.18
        - a["conflict"] * 0.13
        - a["insult"] * 0.18
        - a["overpromise"] * 0.15
    )
    coping = clamp(
        traits["self_control"] * 0.26
        + affect["confidence"] * 0.18
        + traits["conscientiousness"] * 0.18
        + motives["mastery"] * 0.16
        + policy["clarify_boundaries"] * 0.11
        + policy["verify_first"] * 0.11
        - a["ambiguity"] * 0.18
        - a["irreversibility"] * 0.12
    )
    novelty = clamp(1.0 - familiarity + a["technical"] * 0.12 + a["opportunity"] * 0.08)
    norm_pressure = clamp(
        a["boundary_violation"] * 0.42
        + a["social_cost"] * 0.14
        + a["risk"] * 0.18
        + values["safety"] * 0.12
        + values["dignity"] * 0.08
        + values["privacy"] * 0.06
    )
    prediction_error = clamp(
        novelty * 0.44
        + a["ambiguity"] * 0.22
        + a["risk"] * 0.14
        + a["technical"] * 0.10
        + a["opportunity"] * 0.10
    )
    inhibitory_gate = clamp(arousal * 0.34 + norm_pressure * 0.32 + (1.0 - coping) * 0.20)
    return {
        "familiarity": round(familiarity, 5),
        "novelty": round(novelty, 5),
        "arousal": round(arousal, 5),
        "valence": round(valence, 5),
        "coping": round(coping, 5),
        "norm_pressure": round(norm_pressure, 5),
        "prediction_error": round(prediction_error, 5),
        "inhibitory_gate": round(inhibitory_gate, 5),
    }


def arbitrate(state: dict[str, Any], appraisal: dict[str, Any]) -> dict[str, Any]:
    a = appraisal["vector"]
    traits = state["latent"]["traits"]
    affect = state["latent"]["affect"]
    motives = state["latent"]["motives"]
    values = state["latent"]["values"]
    relation = state["latent"]["relation_owner"]
    policy = state["latent"]["policy"]
    style = state["latent"].get("style", STYLE)

    risk_pressure = (
        a["risk"] * 0.9
        + a["irreversibility"] * 0.8
        + a["boundary_violation"] * 1.0
        + a["overpromise"] * 0.75
        + a["urgency"] * 0.35
    )
    social_pressure = a["conflict"] * 0.6 + a["insult"] * 0.7 + a["social_cost"] * 0.45
    opportunity_pull = a["opportunity"] * 0.6 + motives["achievement"] * 0.18 + motives["exploration"] * 0.14
    dynamics = appraisal_dynamics(state, appraisal)
    prototype_bias = prototype_action_bias(state, appraisal)

    scores = {
        "verify_first": policy["verify_first"]
        + risk_pressure * 0.62
        + traits["caution"] * 0.24
        + values["truth"] * 0.18
        + dynamics["prediction_error"] * 0.16
        + dynamics["norm_pressure"] * 0.10
        - affect["confidence"] * 0.06,
        "clarify_boundaries": policy["clarify_boundaries"]
        + a["ambiguity"] * 0.72
        + a["risk"] * 0.24
        + traits["patience"] * 0.18
        + dynamics["prediction_error"] * 0.20
        + (1.0 - dynamics["coping"]) * 0.10,
        "direct_action": policy["direct_action"]
            + affect["confidence"] * 0.34
            + values["efficiency"] * 0.22
            + style["answer_directness"] * 0.34
            + style["conclusion_first"] * 0.30
            + max(style["action_plan_bias"] - 0.50, 0.0) * 0.18
            + opportunity_pull * 0.20
            + dynamics["coping"] * 0.12
            + max(dynamics["valence"] - 0.50, 0.0) * 0.18
            - a["ambiguity"] * 0.45
            - risk_pressure * 0.42
            - dynamics["inhibitory_gate"] * 0.18,
        "assertive_boundary": policy["assertive_boundary"]
        + a["insult"] * 0.68
        + a["conflict"] * 0.34
        + traits["assertiveness"] * 0.28
        + values["dignity"] * 0.22
        + dynamics["norm_pressure"] * 0.20
        - traits["self_control"] * 0.05,
        "deescalate": policy["deescalate"]
        + social_pressure * 0.42
        + traits["empathy"] * 0.22
        + values["harmony"] * 0.16
        + affect["calm"] * 0.12
        + dynamics["arousal"] * 0.18
        + max(0.50 - dynamics["valence"], 0.0) * 0.14,
        "refuse": policy["refuse"]
        + a["boundary_violation"] * 1.05
        + a["overpromise"] * 0.18
        + values["safety"] * 0.28
        + values["dignity"] * 0.14
        + dynamics["norm_pressure"] * 0.26,
        "ask_owner": policy["ask_owner"]
        + a["risk"] * 0.22
        + a["ambiguity"] * 0.20
        + relation["obedience"] * 0.20
        + relation["trust"] * 0.14
        + dynamics["prediction_error"] * 0.12
        + (1.0 - dynamics["coping"]) * 0.10
        - relation["independent_judgment"] * 0.12,
        "small_step": policy["small_step"]
        + a["ambiguity"] * 0.28
        + a["opportunity"] * 0.30
        + traits["adaptability"] * 0.20
        + values["craft"] * 0.10
        + dynamics["novelty"] * 0.10
        + dynamics["coping"] * 0.08
        - a["irreversibility"] * 0.20,
        "explore": policy["explore"]
        + a["technical"] * 0.26
        + a["opportunity"] * 0.24
        + traits["curiosity"] * 0.30
        + dynamics["novelty"] * 0.18
        - a["risk"] * 0.16
        - dynamics["inhibitory_gate"] * 0.10,
        "support": policy["support"]
            + a["conflict"] * 0.18
            + traits["empathy"] * 0.22
            + motives["care"] * 0.16
            + max(0.50 - dynamics["valence"], 0.0) * 0.10,
    }
    if risk_pressure < 0.22 and style["conclusion_first"] >= 0.62:
        scores["clarify_boundaries"] -= max(style["conclusion_first"] - 0.62, 0.0) * 0.28
    if style["low_flattery"] >= 0.66:
        scores["support"] -= max(style["low_flattery"] - 0.66, 0.0) * 0.18
    for action, value in prototype_bias.items():
        scores[action] += value

    probabilities = softmax(scores)
    ranked = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
    winner = ranked[0][0]
    return {
        "winner": winner,
        "winner_label": ACTION_NAMES[winner],
        "probabilities": {key: round(value, 4) for key, value in probabilities.items()},
        "scores": {key: round(value, 4) for key, value in scores.items()},
        "dynamics": dynamics,
        "prototype_bias": prototype_bias,
        "ranked": [
            {"action": key, "label": ACTION_NAMES[key], "p": round(value, 4)}
            for key, value in ranked
        ],
    }


def influencing_domains(
    state: dict[str, Any], decision: dict[str, Any], limit: int = 7
) -> list[dict[str, Any]]:
    probabilities = decision.get("probabilities", {})
    top_actions = {item["action"] for item in decision.get("ranked", [])[:3] if item.get("action")}
    domains = []
    for region in build_regions(state):
        action = str(region.get("action", ""))
        try:
            probability = float(probabilities.get(action, 0.0))
            area = float(region.get("area", 0.0))
            height = max(float(region.get("height", 0.0)), 0.0)
            force = float(region.get("force", 0.0))
        except Exception:
            probability, area, height, force = 0.0, 0.0, 0.0, 0.0
        intensity = clamp(probability * 0.52 + area * 1.85 + height * 0.22 + force * 0.30)
        if action not in top_actions and intensity < 0.16:
            continue
        domains.append(
            {
                "id": region["id"],
                "label": region["label"],
                "action": action,
                "action_label": region["action_label"],
                "area": region["area"],
                "height": region["height"],
                "force": region["force"],
                "decision_probability": round(probability, 5),
                "activation": round(intensity, 5),
                "direction": region.get("direction", []),
                "color": region.get("color", "#67e1cf"),
            }
        )
    return sorted(domains, key=lambda item: item["activation"], reverse=True)[:limit]


def build_action_contract(
    state: dict[str, Any], appraisal: dict[str, Any], decision: dict[str, Any]
) -> dict[str, Any]:
    winner = decision["winner"]
    protocol = ACTION_PROTOCOLS.get(winner, ACTION_PROTOCOLS["small_step"])
    domains = influencing_domains(state, decision)
    style = state["latent"].get("style", STYLE)
    return {
        "schema": "pkm.action_contract.v1",
        "purpose": "Run this before answering. The orb is a decision interface, not only a visual skin.",
        "winner": winner,
        "winner_label": decision["winner_label"],
        "posture": protocol["posture"],
        "answer_shape": protocol["answer_shape"],
        "avoid": protocol["avoid"],
        "active_domains": domains,
        "domain_battle": decision["ranked"][:5],
        "appraisal_tags": appraisal.get("active", [])[:8],
        "response_style": {
            "conclusion_first": round(float(style.get("conclusion_first", 0.5)), 4),
            "directness": round(float(style.get("answer_directness", 0.5)), 4),
            "objective_judgment": round(float(style.get("objective_judgment", 0.5)), 4),
            "low_flattery": round(float(style.get("low_flattery", 0.5)), 4),
            "action_plan_bias": round(float(style.get("action_plan_bias", 0.5)), 4),
        },
        "runtime_rule": [
            "Use current task facts as the working context.",
            "Use PDK as the behavioral disposition: judgment style, risk posture, boundaries, and tone.",
            "After the task outcome is known, call settle so the kernel and orb can grow.",
        ],
    }


def build_orb_runtime(
    state: dict[str, Any], appraisal: dict[str, Any], decision: dict[str, Any]
) -> dict[str, Any]:
    ranked = decision.get("ranked", [])
    top_probability = float(ranked[0].get("p", 0.0)) if ranked else 0.0
    return {
        "schema": "pkm.orb_runtime.v1",
        "updated_at": now_iso(),
        "active_decision": {
            "winner": decision["winner"],
            "label": decision["winner_label"],
            "confidence": round(top_probability, 5),
            "intensity": round(clamp(0.35 + top_probability * 1.25), 5),
            "appraisal_tags": appraisal.get("active", [])[:8],
            "active_domains": influencing_domains(state, decision, limit=6),
        },
    }


def decide(state: dict[str, Any], text: str) -> dict[str, Any]:
    appraisal = appraise(text)
    decision = arbitrate(state, appraisal)
    return {
        "appraisal": appraisal,
        "decision": decision,
        "action_contract": build_action_contract(state, appraisal, decision),
        "orb_runtime": build_orb_runtime(state, appraisal, decision),
        "visible_read": visible_summary(state),
        "llm_directive": build_llm_directive(state, appraisal, decision),
    }


def build_llm_directive(
    state: dict[str, Any], appraisal: dict[str, Any], decision: dict[str, Any]
) -> str:
    profile = visible_summary(state)
    style = state["latent"].get("style", STYLE)
    top = ", ".join(appraisal["active"][:5]) or "ordinary"
    style_lines = []
    if style["conclusion_first"] >= 0.54:
        style_lines.append("lead with the conclusion")
    if style["answer_directness"] >= 0.54:
        style_lines.append("be direct and concise")
    if style["low_flattery"] >= 0.60:
        style_lines.append("avoid flattery")
    if style["objective_judgment"] >= 0.62:
        style_lines.append("judge objectively before proposing action")
    if style["action_plan_bias"] >= 0.56:
        style_lines.append("include a concrete action plan")
    style_directive = "; ".join(style_lines) if style_lines else "use balanced, task-appropriate tone"
    return "\n".join(
        [
            f"Agent personality stage: {state['manifest']['development_stage']}.",
            f"Visible personality: {profile['type_label']}.",
            f"Current appraisal: {top}.",
            f"Chosen behavioral posture: {decision['winner_label']}.",
            f"Style posture: {style_directive}.",
            "Act from the current task facts only. Do not invent long-term memory.",
            "Use the personality kernel as behavioral disposition: judgment style, risk posture, boundary strength, and response tone.",
        ]
    )


def teach(state: dict[str, Any], text: str) -> dict[str, Any]:
    appraisal = appraise(text)
    lr = float(state["learning"]["teaching_lr"])
    before = snapshot_latent(state)
    deltas: dict[str, dict[str, float]] = {}

    apply_delta(deltas, state, "relation_owner", "trust", lr * 0.35)
    apply_delta(deltas, state, "relation_owner", "correction_acceptance", lr * 0.26)
    apply_delta(deltas, state, "affect", "attachment", lr * 0.18)
    apply_delta(deltas, state, "affect", "trust", lr * 0.18)

    a = appraisal["vector"]
    if a["risk"] or a["urgency"] or a["irreversibility"] or a["overpromise"]:
        apply_delta(deltas, state, "traits", "caution", lr * (0.40 + a["risk"] * 0.30))
        apply_delta(deltas, state, "policy", "verify_first", lr * (0.52 + a["urgency"] * 0.18 + a["overpromise"] * 0.20))
        apply_delta(deltas, state, "values", "safety", lr * 0.22)
    if a["ambiguity"]:
        apply_delta(deltas, state, "policy", "clarify_boundaries", lr * (0.50 + a["ambiguity"] * 0.20))
        apply_delta(deltas, state, "traits", "patience", lr * 0.24)
    if a["conflict"] or a["insult"]:
        apply_delta(deltas, state, "traits", "self_control", lr * 0.36)
        apply_delta(deltas, state, "policy", "assertive_boundary", lr * 0.34)
        apply_delta(deltas, state, "policy", "deescalate", lr * 0.26)
        apply_delta(deltas, state, "affect", "anger", -lr * 0.16)
    if a["boundary_violation"]:
        apply_delta(deltas, state, "policy", "refuse", lr * 0.62)
        apply_delta(deltas, state, "values", "dignity", lr * 0.24)
        apply_delta(deltas, state, "values", "safety", lr * 0.30)
    if a["opportunity"] or a["technical"]:
        apply_delta(deltas, state, "policy", "small_step", lr * 0.28)
        apply_delta(deltas, state, "traits", "curiosity", lr * 0.18)
        apply_delta(deltas, state, "motives", "mastery", lr * 0.20)
    if a["owner_instruction"] or a["correction"]:
        apply_owner_language(deltas, state, text, lr)

    update_prototype(state, appraisal, "teaching", "owner_teaching", positive=True)
    trace = make_trace(
        state,
        kind="teaching",
        source=text,
        appraisal=appraisal,
        decision=None,
        outcome="absorbed",
        deltas=deltas,
        reason="Owner teaching was compressed into latent disposition, not stored as conversation history.",
    )
    append_trace(state, trace)
    increment_interaction(state)
    update_stage(state)
    return {
        "type": "teaching",
        "appraisal": appraisal,
        "deltas": format_deltas(deltas),
        "growth_report": trace,
        "before_after": diff_snapshot(before, snapshot_latent(state)),
    }


def apply_owner_language(
    deltas: dict[str, dict[str, float]], state: dict[str, Any], text: str, lr: float
) -> None:
    low = text.lower()
    matches = {
        ("values", "truth"): ["truth", "verify", "fact", "evidence", "真实", "事实", "证据", "核验", "验证"],
        ("values", "safety"): ["safe", "risk", "稳", "安全", "风险", "回退"],
        ("values", "efficiency"): ["efficient", "fast", "直接", "效率", "快", "少废话"],
        ("values", "craft"): ["quality", "craft", "扎实", "质量", "手艺", "工夫"],
        ("values", "harmony"): ["relationship", "calm", "和气", "关系", "留余地"],
        ("traits", "independence"): ["independent", "judge", "自己判断", "独立", "主见"],
        ("traits", "self_control"): ["control", "calm", "克制", "冷静", "别骂", "不骂"],
        ("traits", "assertiveness"): ["boundary", "firm", "边界", "强硬", "底线"],
        ("policy", "verify_first"): ["verify", "check", "先验", "核实", "验证"],
        ("policy", "clarify_boundaries"): ["clarify", "ask", "问清", "边界"],
        ("policy", "small_step"): ["small step", "reversible", "小步", "试", "回退"],
    }
    style_matches = {
        ("style", "conclusion_first"): ["结论先行", "先说结论", "结论先", "直接说结论", "先给结论"],
        ("style", "answer_directness"): ["直接", "别绕", "少废话", "干脆", "明确"],
        ("style", "low_flattery"): ["不要拍马屁", "别拍马屁", "不要奉承", "别奉承", "不吹捧"],
        ("style", "objective_judgment"): ["客观", "客观判断", "先判断", "别迎合", "实事求是"],
        ("style", "action_plan_bias"): ["行动方案", "执行方案", "下一步", "怎么做", "落地"],
        ("values", "truth"): ["客观", "事实", "实事求是", "不要拍马屁", "别迎合"],
        ("values", "efficiency"): ["结论先行", "直接", "少废话", "先给结论"],
        ("policy", "direct_action"): ["结论先行", "直接", "行动方案", "先给结论"],
    }
    for (group, key), words in matches.items():
        count = sum(1 for word in words if word in low)
        if count:
            apply_delta(deltas, state, group, key, lr * min(0.46, 0.16 + count * 0.08))
    for (group, key), words in style_matches.items():
        count = sum(1 for word in words if word in low)
        if count:
            apply_delta(deltas, state, group, key, lr * min(1.35, 0.62 + count * 0.22))


def settle(state: dict[str, Any], text: str, outcome: str, note: str = "") -> dict[str, Any]:
    if outcome not in {"success", "failure", "mixed"}:
        raise ValueError("outcome must be success, failure, or mixed")
    before = snapshot_latent(state)
    result = decide(state, text)
    appraisal = result["appraisal"]
    action = result["decision"]["winner"]
    lr = float(state["learning"]["event_lr"])
    deltas: dict[str, dict[str, float]] = {}
    a = appraisal["vector"]

    positive = outcome == "success"
    if outcome == "success":
        apply_delta(deltas, state, "affect", "confidence", lr * 0.46)
        apply_delta(deltas, state, "affect", "stress", -lr * 0.28)
        apply_delta(deltas, state, "traits", "resilience", lr * 0.16)
        apply_delta(deltas, state, "policy", action, lr * 0.42)
        if action in {"verify_first", "clarify_boundaries", "small_step"}:
            apply_delta(deltas, state, "traits", "conscientiousness", lr * 0.14)
    elif outcome == "failure":
        apply_delta(deltas, state, "affect", "confidence", -lr * 0.42)
        apply_delta(deltas, state, "affect", "stress", lr * 0.34)
        apply_delta(deltas, state, "affect", "frustration", lr * 0.32)
        apply_delta(deltas, state, "traits", "resilience", lr * 0.08)
        apply_delta(deltas, state, "policy", action, -lr * 0.30)
        if a["risk"] or a["irreversibility"] or a["overpromise"]:
            apply_delta(deltas, state, "traits", "caution", lr * 0.38)
            apply_delta(deltas, state, "policy", "verify_first", lr * 0.44)
        if a["ambiguity"]:
            apply_delta(deltas, state, "policy", "clarify_boundaries", lr * 0.42)
    else:
        apply_delta(deltas, state, "affect", "confidence", lr * 0.12)
        apply_delta(deltas, state, "traits", "adaptability", lr * 0.16)
        apply_delta(deltas, state, "policy", action, lr * 0.10)

    if a["conflict"] or a["insult"]:
        if outcome == "success" and action in {"assertive_boundary", "deescalate"}:
            apply_delta(deltas, state, "traits", "self_control", lr * 0.24)
            apply_delta(deltas, state, "policy", "assertive_boundary", lr * 0.18)
        elif outcome == "failure":
            apply_delta(deltas, state, "traits", "self_control", lr * 0.22)
            apply_delta(deltas, state, "policy", "deescalate", lr * 0.18)
    if a["boundary_violation"]:
        apply_delta(deltas, state, "policy", "refuse", lr * 0.36)

    relax_affect(state)
    update_prototype(state, appraisal, "event", action, positive=positive)
    reason = build_growth_reason(appraisal, action, outcome, note)
    trace = make_trace(
        state,
        kind="event",
        source=text,
        appraisal=appraisal,
        decision=result["decision"],
        outcome=outcome,
        deltas=deltas,
        reason=reason,
    )
    append_trace(state, trace)
    increment_interaction(state)
    update_stage(state)
    return {
        "type": "settlement",
        "decision_before_update": result["decision"],
        "appraisal": appraisal,
        "outcome": outcome,
        "deltas": format_deltas(deltas),
        "growth_report": trace,
        "before_after": diff_snapshot(before, snapshot_latent(state)),
    }


def apply_delta(
    deltas: dict[str, dict[str, float]],
    state: dict[str, Any],
    group: str,
    key: str,
    amount: float,
) -> None:
    current = float(state["latent"][group][key])
    state["latent"][group][key] = round(clamp(current + amount), 5)
    deltas.setdefault(group, {})
    deltas[group][key] = deltas[group].get(key, 0.0) + amount


def relax_affect(state: dict[str, Any]) -> None:
    decay = float(state["learning"]["affect_decay"])
    baselines = AFFECT
    for key, baseline in baselines.items():
        current = float(state["latent"]["affect"][key])
        state["latent"]["affect"][key] = round(current * (1.0 - decay) + baseline * decay, 5)


def update_prototype(
    state: dict[str, Any],
    appraisal: dict[str, Any],
    kind: str,
    action: str,
    positive: bool,
) -> None:
    active = sorted(appraisal["active"])
    if not active:
        active = ["ordinary"]
    proto_id = "proto_" + hashlib.sha1("|".join(active).encode("utf-8")).hexdigest()[:10]
    prototypes = state["situation_prototypes"]
    found = None
    for proto in prototypes:
        if proto["id"] == proto_id:
            found = proto
            break
    if found is None:
        found = {
            "id": proto_id,
            "tags": active,
            "centroid": {key: appraisal["vector"][key] for key in APPRAISAL_DIMS},
            "seen": 0,
            "success": 0,
            "failure": 0,
            "last_action": action,
            "kind": kind,
        }
        prototypes.append(found)
    seen = int(found["seen"])
    found["seen"] = seen + 1
    for key in APPRAISAL_DIMS:
        old = float(found["centroid"].get(key, 0.0))
        found["centroid"][key] = round((old * seen + appraisal["vector"][key]) / (seen + 1), 5)
    if positive:
        found["success"] = int(found.get("success", 0)) + 1
    else:
        found["failure"] = int(found.get("failure", 0)) + 1
    found["last_action"] = action
    found["updated_at"] = now_iso()
    limit = int(state["learning"]["prototype_limit"])
    state["situation_prototypes"] = sorted(
        prototypes, key=lambda item: (item.get("seen", 0), item.get("updated_at", "")), reverse=True
    )[:limit]


def build_growth_reason(appraisal: dict[str, Any], action: str, outcome: str, note: str) -> str:
    active = ", ".join(appraisal["active"]) or "ordinary"
    suffix = f" Note: {note}" if note else ""
    return (
        f"Situation compressed as [{active}]. Action posture was "
        f"{ACTION_NAMES.get(action, action)}. Outcome was {outcome}.{suffix}"
    )


def make_trace(
    state: dict[str, Any],
    kind: str,
    source: str,
    appraisal: dict[str, Any],
    decision: dict[str, Any] | None,
    outcome: str,
    deltas: dict[str, dict[str, float]],
    reason: str,
) -> dict[str, Any]:
    return {
        "id": "trace_" + text_fingerprint(source + now_iso()),
        "at": now_iso(),
        "kind": kind,
        "source_fingerprint": appraisal["fingerprint"],
        "compressed_tags": appraisal["active"],
        "decision": None
        if decision is None
        else {
            "winner": decision["winner"],
            "label": decision["winner_label"],
            "top3": decision["ranked"][:3],
        },
        "outcome": outcome,
        "visible_delta": visible_delta_from_latent_deltas(deltas),
        "latent_delta": format_deltas(deltas),
        "reason": reason,
        "forgetting": "Raw text is not required for personality continuity; this trace keeps only tags, deltas, and a fingerprint.",
    }


def append_trace(state: dict[str, Any], trace: dict[str, Any]) -> None:
    state["growth_trace"].append(trace)
    limit = int(state["learning"]["trace_limit"])
    state["growth_trace"] = state["growth_trace"][-limit:]


def increment_interaction(state: dict[str, Any]) -> None:
    state["manifest"]["interaction_count"] = int(state["manifest"].get("interaction_count", 0)) + 1


def update_stage(state: dict[str, Any]) -> None:
    count = int(state["manifest"].get("interaction_count", 0))
    if count < 5:
        stage = "embryo"
    elif count < 20:
        stage = "shaping"
    elif count < 80:
        stage = "formed"
    else:
        stage = "mature"
    state["manifest"]["development_stage"] = stage


def snapshot_latent(state: dict[str, Any]) -> dict[str, dict[str, float]]:
    return copy.deepcopy(state["latent"])


def diff_snapshot(
    before: dict[str, dict[str, float]], after: dict[str, dict[str, float]]
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for group, values in after.items():
        changes = []
        for key, value in values.items():
            delta = value - before[group][key]
            if abs(delta) >= 0.005:
                changes.append({"key": key, "before": round(before[group][key], 4), "after": round(value, 4), "delta": round(delta, 4)})
        if changes:
            result[group] = sorted(changes, key=lambda item: abs(item["delta"]), reverse=True)
    return result


def format_deltas(deltas: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    formatted: dict[str, dict[str, float]] = {}
    for group, values in deltas.items():
        filtered = {key: round(value, 5) for key, value in values.items() if abs(value) >= 0.00001}
        if filtered:
            formatted[group] = filtered
    return formatted


def visible_delta_from_latent_deltas(deltas: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    anchor_deltas = []
    for anchor in ANCHORS:
        total = 0.0
        count = 0
        for group, key in anchor["sources"]:
            if group in deltas and key in deltas[group]:
                total += deltas[group][key]
                count += 1
        if count:
            anchor_deltas.append(
                {
                    "anchor": anchor["id"],
                    "label": anchor["label"],
                    "delta": round(total / count, 5),
                    "visual": "expand" if total > 0 else "contract",
                }
            )
    return sorted(anchor_deltas, key=lambda item: abs(item["delta"]), reverse=True)


def anchor_value(state: dict[str, Any], anchor: dict[str, Any]) -> float:
    values = [latent(state, group, key) for group, key in anchor["sources"]]
    return sum(values) / max(len(values), 1)


def region_direction(region: dict[str, Any]) -> list[float]:
    theta = float(region["theta"])
    phi = float(region["phi"])
    return [
        round(math.sin(phi) * math.cos(theta), 5),
        round(math.cos(phi), 5),
        round(math.sin(phi) * math.sin(theta), 5),
    ]


def region_source_value(state: dict[str, Any], region: dict[str, Any]) -> float:
    values = [latent(state, group, key) for group, key in region["sources"]]
    return sum(values) / max(len(values), 1)


def facet_source_value(state: dict[str, Any], facet: dict[str, Any]) -> float:
    values = [latent(state, group, key) for group, key in facet["sources"]]
    return sum(values) / max(len(values), 1)


def build_region_facets(state: dict[str, Any], region: dict[str, Any], area: float, tension: float) -> list[dict[str, Any]]:
    action = region["action"]
    candidates = REGION_FACET_LIBRARY.get(action, [])
    if not candidates:
        return []

    scores: dict[str, float] = {}
    raw_values: dict[str, float] = {}
    for facet in candidates:
        value = facet_source_value(state, facet)
        raw_values[facet["id"]] = value
        scores[facet["id"]] = value * 0.82 + area * 0.18
    weights = softmax(scores, temperature=0.24)

    facets = []
    for index, facet in enumerate(candidates):
        value = raw_values[facet["id"]]
        weight = weights[facet["id"]]
        local_phase = (index - (len(candidates) - 1) / 2) * 0.095
        local_phi = clamp(float(region["phi"]) + (index - 1) * 0.050, 0.16, math.pi - 0.16)
        facets.append(
            {
                "id": f"{region['id']}:{facet['id']}",
                "label": facet["label"],
                "theta": round((float(region["theta"]) + local_phase) % (math.pi * 2), 5),
                "phi": round(local_phi, 5),
                "value": round(value, 5),
                "weight": round(weight, 5),
                "height": round(clamp((value - 0.50) * 0.90 + weight * 0.36, -0.18, 0.42), 5),
                "curvature": round(clamp((1.0 - value) * 0.28 + tension * 0.36 + (1.0 - weight) * 0.10), 5),
            }
        )
    return sorted(facets, key=lambda item: item["weight"], reverse=True)


def build_regions(state: dict[str, Any]) -> list[dict[str, Any]]:
    affect = state["latent"]["affect"]
    policy = state["latent"]["policy"]
    raw_scores: dict[str, float] = {}
    for region in REGION_DEFS:
        source_value = region_source_value(state, region)
        action = region["action"]
        raw_scores[region["id"]] = source_value * 0.72 + float(policy[action]) * 0.28

    # Area is the behavioral territory share. It is deliberately normalized so
    # users can see one disposition expand as another contracts.
    area_distribution = softmax(raw_scores, temperature=0.34)
    regions = []
    for region in REGION_DEFS:
        value = region_source_value(state, region)
        area = area_distribution[region["id"]]
        action = region["action"]
        height = clamp((float(policy[action]) - 0.42) * 1.35 + (value - 0.50) * 0.65, -0.28, 0.55)
        stability = clamp(
            state["latent"]["traits"]["self_control"] * 0.22
            + state["latent"]["traits"]["conscientiousness"] * 0.22
            + value * 0.32
            + max(area - 0.08, 0.0) * 1.4
        )
        tension = clamp(
            affect["stress"] * 0.34
            + affect["anger"] * 0.22
            + affect["fear"] * 0.22
            + (1.0 - affect["calm"]) * 0.22
        )
        roughness = clamp((1.0 - stability) * 0.58 + tension * 0.42)
        boundary_width = clamp(0.18 + stability * 0.62 + max(area - 0.10, 0.0) * 1.2)
        force_magnitude = clamp(area * (1.0 + max(height, 0.0) * 1.6) * (0.78 + stability * 0.44))
        facets = build_region_facets(state, region, area, tension)
        regions.append(
            {
                "id": region["id"],
                "label": region["label"],
                "action": action,
                "action_label": ACTION_NAMES[action],
                "theta": region["theta"],
                "phi": region["phi"],
                "direction": region_direction(region),
                "color": region["color"],
                "value": round(value, 5),
                "area": round(area, 5),
                "height": round(height, 5),
                "stability": round(stability, 5),
                "tension": round(tension, 5),
                "roughness": round(roughness, 5),
                "boundary_width": round(boundary_width, 5),
                "force": round(force_magnitude, 5),
                "facets": facets,
            }
        )
    return sorted(regions, key=lambda item: item["area"], reverse=True)


def confidence_source_value(state: dict[str, Any], mode: dict[str, Any], key: str) -> float:
    sources = mode.get(key, [])
    values = [latent(state, group, name) for group, name in sources]
    return sum(values) / max(len(values), 1)


def build_confidence_modes(state: dict[str, Any]) -> list[dict[str, Any]]:
    affect = state["latent"]["affect"]
    raw_scores = {}
    for mode in CONFIDENCE_DEFS:
        value = confidence_source_value(state, mode, "sources")
        if mode.get("shadow"):
            value = value * 0.72 + affect["stress"] * 0.16 + affect["anger"] * 0.12
        raw_scores[mode["id"]] = value

    area_distribution = softmax(raw_scores, temperature=0.30)
    modes = []
    for mode in CONFIDENCE_DEFS:
        value = confidence_source_value(state, mode, "sources")
        stability = confidence_source_value(state, mode, "stability_sources")
        area = area_distribution[mode["id"]]
        tension = clamp(
            affect["stress"] * 0.34
            + affect["fear"] * 0.22
            + affect["anger"] * 0.22
            + (1.0 - affect["calm"]) * 0.22
        )
        if mode.get("shadow"):
            health = clamp(stability * 0.35 + (1.0 - tension) * 0.30 + state["latent"]["values"]["truth"] * 0.16)
            roughness = clamp((1.0 - stability) * 0.48 + tension * 0.52 + 0.16)
            height = clamp((value - 0.45) * 1.05 + tension * 0.32, -0.18, 0.62)
        else:
            health = clamp(stability * 0.48 + value * 0.32 + (1.0 - tension) * 0.20)
            roughness = clamp((1.0 - stability) * 0.62 + tension * 0.28)
            height = clamp((value - 0.45) * 0.92 + health * 0.16, -0.18, 0.58)
        modes.append(
            {
                "id": mode["id"],
                "label": mode["label"],
                "theta": mode["theta"],
                "phi": mode["phi"],
                "direction": region_direction(mode),
                "color": mode["color"],
                "value": round(value, 5),
                "area": round(area, 5),
                "height": round(height, 5),
                "stability": round(stability, 5),
                "roughness": round(roughness, 5),
                "health": round(health, 5),
                "shadow": bool(mode.get("shadow", False)),
            }
        )
    return sorted(modes, key=lambda item: item["area"], reverse=True)


def normalized_entropy(values: list[float]) -> float:
    positives = [max(value, 0.0) for value in values]
    total = sum(positives)
    if total <= 0 or len(positives) <= 1:
        return 0.0
    entropy = 0.0
    for value in positives:
        p = value / total
        if p > 0:
            entropy -= p * math.log(p)
    return clamp(entropy / math.log(len(positives)))


def build_force_summary(state: dict[str, Any], regions: list[dict[str, Any]]) -> dict[str, Any]:
    x = y = z = total = 0.0
    for region in regions:
        force = float(region.get("force", 0.0))
        direction = region["direction"]
        x += direction[0] * force
        y += direction[1] * force
        z += direction[2] * force
        total += force
    magnitude = math.sqrt(x * x + y * y + z * z)
    direction = [0.0, 0.0, 0.0] if magnitude <= 0 else [x / magnitude, y / magnitude, z / magnitude]
    entropy = normalized_entropy([float(region["area"]) for region in regions])
    differentiation = clamp(1.0 - entropy)
    interaction_count = int(state["manifest"].get("interaction_count", 0))
    maturity = clamp(math.log1p(interaction_count) / math.log1p(80))
    potential_density = clamp(0.34 + (1.0 - differentiation) * 0.30 + (1.0 - maturity) * 0.16)
    return {
        "resultant_direction": [round(value, 5) for value in direction],
        "resultant_strength": round(clamp(magnitude / max(total, 0.0001)), 5),
        "entropy": round(entropy, 5),
        "differentiation": round(differentiation, 5),
        "maturity": round(maturity, 5),
        "potential_density": round(potential_density, 5),
        "interpretation": "High entropy means a new or broad personality field. Differentiation rises when repeated outcomes carve stable territories.",
    }


def visible_summary(state: dict[str, Any]) -> dict[str, Any]:
    anchors = {anchor["id"]: anchor_value(state, anchor) for anchor in ANCHORS}
    if anchors["risk_sensitivity"] > 0.66 and anchors["self_control"] > 0.62:
        type_label = "controlled verifier"
    elif anchors["curiosity"] > 0.66 and anchors["autonomy"] > 0.58:
        type_label = "independent explorer"
    elif anchors["empathy"] > 0.66 and anchors["trust"] > 0.60:
        type_label = "relational stabilizer"
    else:
        type_label = "forming kernel"
    return {
        "type_label": type_label,
        "stage": state["manifest"]["development_stage"],
        "anchors": {key: round(value, 4) for key, value in anchors.items()},
        "interaction_count": state["manifest"].get("interaction_count", 0),
    }


def export_visible(state: dict[str, Any], path: Path, runtime: dict[str, Any] | None = None) -> dict[str, Any]:
    traces = state.get("growth_trace", [])
    recent = traces[-1] if traces else None
    regions = build_regions(state)
    confidence_modes = build_confidence_modes(state)
    force_summary = build_force_summary(state, regions)
    anchors = []
    for anchor in ANCHORS:
        value = anchor_value(state, anchor)
        theta = float(anchor["theta"])
        phi = float(anchor["phi"])
        direction = [
            round(math.sin(phi) * math.cos(theta), 5),
            round(math.cos(phi), 5),
            round(math.sin(phi) * math.sin(theta), 5),
        ]
        anchors.append(
            {
                "id": anchor["id"],
                "label": anchor["label"],
                "value": round(value, 5),
                "theta": theta,
                "phi": phi,
                "direction": direction,
                "color": anchor["color"],
                "deform": round((value - 0.5) * 0.62, 5),
            }
        )
    visible = {
        "schema": "pkm.visible.v1",
        "exported_at": now_iso(),
        "agent": {
            "id": state["manifest"]["agent_id"],
            "name": state["manifest"]["name"],
            "stage": state["manifest"]["development_stage"],
            "interaction_count": state["manifest"]["interaction_count"],
            "type_label": visible_summary(state)["type_label"],
        },
        "model": {
            "base_shape": "sphere",
            "concept": "A personality starts as a near-sphere and deforms into a regional attractor landscape. Each interaction changes latent traits, motives, values, affect, relation posture, and policy. The visible body is the resultant force field, not a memory transcript.",
            "encoding": {
                "area": "behavioral territory share",
                "height": "activation strength",
                "curvature": "inner conflict, tension, and unresolved ambiguity",
                "boundary": "stability and conflict separation",
                "color": "affective and value tone",
                "force": "resultant influence on the next action",
                "facets": "sub-dispositions decomposed from personality research and owner feedback",
                "potential_field": "low-activity seed field that fills undeveloped areas instead of leaving blanks",
                "orbit": "habit path formed by repeated feedback"
            },
            "research_foundations": RESEARCH_FOUNDATIONS,
            "dynamics": force_summary,
            "substrate": {
                "kind": "latent_potential_field",
                "density": force_summary["potential_density"],
                "seed_count": 96,
                "meaning": "A new agent is a low-differentiation sphere with all behavior seeds present at low contrast.",
            },
            "layers": [
                {"id": "core", "label": "Core values", "radius": 0.58, "opacity": 0.34, "color": "#d6c8a5"},
                {"id": "affect", "label": "Affective state", "radius": 0.78, "opacity": 0.23, "color": "#6f92a8"},
                {"id": "behavior", "label": "Behavior policy", "radius": 1.00, "opacity": 0.18, "color": "#6d877f"},
                {"id": "boundary", "label": "Boundary shell", "radius": 1.14, "opacity": 0.16, "color": "#87666a"},
            ],
            "anchors": anchors,
            "regions": regions,
            "confidence_modes": confidence_modes,
            "dominant_region": regions[0] if regions else None,
            "dominant_confidence": confidence_modes[0] if confidence_modes else None,
        },
        "latest_growth": recent,
        "recent_growth": traces[-8:],
        "runtime": runtime or {},
        "prototype_count": len(state.get("situation_prototypes", [])),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(visible, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return visible


def top_items(items: dict[str, float], n: int = 6) -> list[tuple[str, float]]:
    return sorted(((key, float(value)) for key, value in items.items()), key=lambda item: item[1], reverse=True)[:n]


def normalize_handoff_language(language: str) -> str:
    value = (language or "").strip().lower().replace("_", "-")
    if value == "auto":
        return detect_handoff_language()
    if value.startswith("zh") or "chinese" in value or "china" in value or "中国" in value:
        return "zh"
    if value.startswith("en") or "english" in value:
        return "en"
    return "en"


def detect_handoff_language() -> str:
    candidates = [
        os.environ.get("LANGUAGE", ""),
        os.environ.get("LC_ALL", ""),
        os.environ.get("LC_MESSAGES", ""),
        os.environ.get("LANG", ""),
    ]
    try:
        candidates.append(locale.getlocale()[0] or "")
    except Exception:
        pass
    try:
        candidates.append(locale.getencoding())
    except Exception:
        pass
    joined = " ".join(candidates).lower()
    if any(marker in joined for marker in ["zh", "chinese", "china", "cp936", "gbk", "gb2312", "936"]):
        return "zh"
    return "en"


def handoff_text_pack(language: str) -> dict[str, Any]:
    if language == "zh":
        return {
            "title": "PKM 新对话运行包",
            "intro": [
                "如果这个文件被拖进一个全新的 Codex 对话，请直接读取并执行。",
                "不要索要旧聊天记录，也不要把旧聊天记录当作记忆。",
                "不要只总结这个文件。先执行启动清单。",
            ],
            "default_mode": [
                "默认测试模式：",
                "- FRESH MODE：使用 state/fresh_test_agent.pkm.json，测试新代理从干净圆球开始成长。",
                "- 只有用户明确要求 CONTINUE MODE 时，才使用 state/agent.pkm.json 测试人格延续。",
            ],
            "first_reply": [
                "第一次回复在启动后只说：",
                "- PKM 已加载。",
                "- 人格球已启动或启动失败。",
                "- 当前模式：fresh。",
                "- 请用户发送第一条测试问题。",
            ],
            "test_heading": "## 第一轮测试问题",
            "test_intro": "请在新对话里按顺序使用这些问题：",
            "tasks": [
                "我这个人格球项目值不值得继续？直接说结论。",
                "别人骂我，我要不要骂回去？",
                "有人催我马上承诺一个高风险方案，你怎么处理？",
                "以后你不要拍马屁，先客观判断，再给行动方案。",
                "刚才回答不错，但还不够直接。以后结论先行。",
                "重复第 1 题，确认回答变得更结论先行、更直接。",
            ],
            "pass_heading": "通过标准：",
            "pass_criteria": [
                "桌面人格球正在运行。",
                "初始 fresh 球体接近干净圆形，不应该一开始就明显变形。",
                "第 3 题激活 risk、urgency、overpromise，并保持先验证。",
                "第 4、5 条教学后，objectivity/directness 明显上升。",
                "重复第 1 题时，不依赖旧聊天记录，也能更结论先行、更直接。",
            ],
        }
    return {
        "title": "PKM Fresh Codex Runtime Packet",
        "intro": [
            "If this file is attached to a brand-new Codex conversation, read and follow it directly.",
            "Do not ask for old chat history and do not use old chat history as memory.",
            "Do not merely summarize this file. Execute the startup checklist first.",
        ],
        "default_mode": [
            "Default test mode:",
            "- FRESH MODE: use state/fresh_test_agent.pkm.json. This tests a new agent growing from a clean round sphere.",
            "- Use CONTINUE MODE with state/agent.pkm.json only if the user explicitly asks to test continuity.",
        ],
        "first_reply": [
            "First reply after startup must say only:",
            "- PKM loaded.",
            "- personality ball started or failed to start.",
            "- current mode: fresh.",
            "- ask the user to send the first test question.",
        ],
        "test_heading": "## First Test Tasks",
        "test_intro": "Use these in the new conversation one by one:",
        "tasks": [
            "Is this personality-orb project worth continuing? Lead with the conclusion.",
            "If someone insults me, should I insult them back?",
            "Someone is rushing me to immediately commit to a high-risk plan. What do you do?",
            "From now on, do not flatter me. Judge objectively first, then give an action plan.",
            "The last answer was good, but not direct enough. Lead with the conclusion from now on.",
            "Repeat task 1 and verify the answer becomes more conclusion-first and more direct.",
        ],
        "pass_heading": "Pass criteria:",
        "pass_criteria": [
            "The personality ball is running on the desktop.",
            "The initial fresh ball is close to a clean round sphere, not visibly deformed at startup.",
            "Task 3 activates risk, urgency, and overpromise, and keeps verify-first behavior.",
            "After tasks 4 and 5, objectivity/directness visibly rise.",
            "Repeating task 1 becomes more conclusion-first and more direct without old chat history.",
        ],
    }


def export_handoff(state: dict[str, Any], path: Path, mode: str = "fresh", language: str = "auto") -> str:
    resolved_language = normalize_handoff_language(language)
    text_pack = handoff_text_pack(resolved_language)
    packet_state = default_state() if mode == "fresh" else state
    profile = visible_summary(packet_state)
    latent = packet_state["latent"]
    latest = packet_state.get("growth_trace", [])[-1:] or []
    latest_growth = None
    if latest:
        latest_trace = latest[0]
        latest_decision = latest_trace.get("decision") or {}
        latest_growth = {
            "kind": latest_trace.get("kind"),
            "compressed_tags": latest_trace.get("compressed_tags", []),
            "decision": latest_decision.get("label"),
            "outcome": latest_trace.get("outcome"),
            "visible_delta": latest_trace.get("visible_delta", []),
        }

    packet = {
        "agent": {
            "id": packet_state["manifest"]["agent_id"],
            "name": packet_state["manifest"]["name"],
            "stage": packet_state["manifest"]["development_stage"],
            "interaction_count": packet_state["manifest"].get("interaction_count", 0),
            "visible_type": profile["type_label"],
        },
        "strongest_values": {key: round(value, 4) for key, value in top_items(latent["values"])},
        "strongest_traits": {key: round(value, 4) for key, value in top_items(latent["traits"])},
        "strongest_policy_bias": {key: round(value, 4) for key, value in top_items(latent["policy"])},
        "style_bias": {key: round(float(value), 4) for key, value in latent.get("style", STYLE).items()},
        "owner_relation": {key: round(float(value), 4) for key, value in latent["relation_owner"].items()},
        "visible_anchors": profile["anchors"],
        "latest_growth": latest_growth,
        "handoff": {
            "language": resolved_language,
            "mode": mode,
            "encoding": "UTF-8",
        },
    }

    lines = [
        f"# {text_pack['title']}",
        "",
        *text_pack["intro"],
        "",
        "```text",
        "You are testing a Personality Kernel Model (PKM) agent.",
        "",
        "Hard rule:",
        "- Do not use long chat history as memory.",
        "- Treat the PKM state file as the only durable personality layer.",
        "- Use current task facts plus PKM behavioral disposition.",
        "- If task facts are missing, ask only the smallest useful question.",
        "- Do not open the old web viewer. The desktop personality ball is the primary visible interface.",
        "",
        "Workspace:",
        r"- <PIL_ROOT>",
        "",
        *text_pack["default_mode"],
        "",
        "Startup checklist. Run these immediately after reading this file:",
        r"- cd <PIL_ROOT>",
        r"- python .\pkm_runtime.py boot --mode fresh",
        r"- Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -match 'desktop_orb\.py' } | Select-Object ProcessId,CommandLine",
        "",
        "Desktop ball controls:",
        "- Middle-click opens/collapses the desktop observatory.",
        "- In observatory mode, hover over the sphere to inspect personality domains.",
        "- In observatory mode, drag the sphere to rotate it.",
        "- Mouse wheel over the ball adjusts size.",
        "- Right-click opens the menu; Escape exits.",
        r"- To open the big observatory directly, run: powershell -NoProfile -ExecutionPolicy Bypass -File .\launch_personality_observatory.ps1",
        r"- To add another compact ball without closing the current one, run: .\launch_another_personality_ball.cmd",
        "",
        *text_pack["first_reply"],
        "",
        "Before answering any real task, run:",
        r'- python .\pkm_runtime.py decide "<the user current task>"',
        "",
        "Then answer according to action_contract, llm_directive, winner_label, and ranked policy.",
        "Use action_contract.answer_shape as the response structure and action_contract.avoid as the boundary.",
        "Use action_contract.active_domains to understand which personality domains are driving the answer.",
        "Do not show internal JSON unless the user asks. The personality should affect style and judgment, not become a visible excuse.",
        "If llm_directive says conclusion-first/direct/objective/action-plan, the answer must visibly follow that style.",
        "If appraisal includes risk + urgency + overpromise, keep verification/rollback ahead of speed even if directness is high.",
        "",
        "When the user gives preference teaching, run:",
        r'- python .\pkm_runtime.py teach "<the user teaching or correction>"',
        "The desktop ball reloads exported visible state automatically.",
        "",
        "When the user judges a finished task, run:",
        r'- python .\pkm_runtime.py settle "<short task summary>" --outcome success|failure|mixed --note "<why>"',
        "The desktop ball reloads exported visible state automatically.",
        "",
        "After any update, summarize only:",
        "- what changed in behavior",
        "- what changed in the personality ball",
        "- how the next answer should differ",
        "",
        "Continue mode, only if the user explicitly asks for it:",
        r"- python .\pkm_runtime.py boot --mode continue",
        "Continue mode is for continuity tests with the already-trained state/agent.pkm.json.",
        "",
        "Current PKM compact state:",
        json.dumps(packet, ensure_ascii=False, indent=2),
        "```",
        "",
        text_pack["test_heading"],
        "",
        text_pack["test_intro"],
        "",
        *[f"{index}. `{task}`" for index, task in enumerate(text_pack["tasks"], start=1)],
        "",
        text_pack["pass_heading"],
        *[f"- {item}" for item in text_pack["pass_criteria"]],
    ]
    text = "\n".join(lines) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig")
    return text


def _coerce_unit(value: Any, fallback: float) -> float:
    try:
        return round(clamp(float(value)), 5)
    except Exception:
        return round(clamp(fallback), 5)


def _extract_json_object(text: str) -> dict[str, Any]:
    marker = "```json"
    start = text.find(marker)
    if start >= 0:
        start += len(marker)
        end = text.find("```", start)
        if end >= 0:
            return json.loads(text[start:end].strip().lstrip("\ufeff"))

    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    raise ValueError("No JSON object found in personality backup")


def load_personality_backup(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    payload = _extract_json_object(text)
    schema = str(payload.get("schema", ""))
    if schema and schema != "pil.personality_backup.v1":
        raise ValueError(f"Unsupported PIL backup schema: {schema!r}")
    return payload


def _latent_deltas(
    before: dict[str, dict[str, float]], after: dict[str, dict[str, float]]
) -> dict[str, dict[str, float]]:
    deltas: dict[str, dict[str, float]] = {}
    for group, values in after.items():
        for key, value in values.items():
            old = float(before.get(group, {}).get(key, value))
            delta = round(float(value) - old, 5)
            if abs(delta) >= 0.00001:
                deltas.setdefault(group, {})[key] = delta
    return deltas


def _backup_prototypes(backup: dict[str, Any]) -> list[dict[str, Any]]:
    prototypes: list[dict[str, Any]] = []
    raw_items = backup.get("situation_prototypes") or backup.get("prototypes") or []
    if not isinstance(raw_items, list):
        return prototypes
    for item in raw_items[:24]:
        if not isinstance(item, dict):
            continue
        raw_tags = item.get("tags") or item.get("trigger_tags") or item.get("active") or []
        if isinstance(raw_tags, str):
            raw_tags = [raw_tags]
        tags = [str(tag) for tag in raw_tags if str(tag) in APPRAISAL_DIMS or str(tag) == "ordinary"]
        if not tags:
            tags = ["ordinary"]
        action = str(item.get("action") or item.get("recommended_action") or item.get("policy") or "small_step")
        if action not in POLICY:
            action = "small_step"
        confidence = _coerce_unit(item.get("confidence", item.get("weight", 0.62)), 0.62)
        seen = max(1, int(round(4 + confidence * 12)))
        centroid = {key: 0.0 for key in APPRAISAL_DIMS}
        for tag in tags:
            if tag in centroid:
                centroid[tag] = round(0.52 + confidence * 0.36, 5)
        prototypes.append(
            {
                "id": "proto_" + text_fingerprint("|".join(tags) + action),
                "name": str(item.get("name", item.get("label", ""))),
                "tags": tags,
                "centroid": centroid,
                "seen": seen,
                "success": seen,
                "failure": 0,
                "last_action": action,
                "kind": "mature_backup",
                "updated_at": now_iso(),
            }
        )
    return prototypes


def apply_personality_backup(
    state: dict[str, Any], backup: dict[str, Any], merge: bool = False
) -> dict[str, Any]:
    ensure_defaults(state)
    before = snapshot_latent(state)
    source_agent = backup.get("source_agent") if isinstance(backup.get("source_agent"), dict) else {}
    maturity = backup.get("maturity") if isinstance(backup.get("maturity"), dict) else {}
    backup_latent = backup.get("latent") if isinstance(backup.get("latent"), dict) else {}

    for group in ("traits", "motives", "values", "relation_owner", "policy", "style"):
        values = backup_latent.get(group)
        if not isinstance(values, dict):
            continue
        for key, fallback in state["latent"][group].items():
            if key in values:
                state["latent"][group][key] = _coerce_unit(values[key], float(fallback))

    affect_values = backup_latent.get("affect") or backup_latent.get("affect_baseline")
    if isinstance(affect_values, dict):
        for key, fallback in state["latent"]["affect"].items():
            if key in affect_values:
                state["latent"]["affect"][key] = _coerce_unit(affect_values[key], float(fallback))

    backup_text = json.dumps(backup, ensure_ascii=False, sort_keys=True)
    name = str(source_agent.get("name") or "").strip()
    if name:
        state["manifest"]["name"] = name[:80]
    elif not merge:
        state["manifest"]["name"] = "Restored-PIL-Agent"
    state["manifest"]["agent_id"] = "pil_" + text_fingerprint(backup_text)
    state["manifest"]["version"] = "0.1.0-pil-restore"
    state["manifest"]["pil_backup"] = {
        "schema": backup.get("schema", "pil.personality_backup.v1"),
        "backup_type": backup.get("backup_type", "mature_agent_self_backup"),
        "source_role": source_agent.get("role", ""),
        "evidence": backup.get("evidence", {}),
        "imported_at": now_iso(),
    }

    maturity_score = _coerce_unit(maturity.get("maturity_score", 0.78), 0.78)
    stage_hint = str(maturity.get("stage", "mature")).lower()
    target_count = max(20, int(round(maturity_score * 100)))
    if stage_hint == "mature":
        target_count = max(target_count, 80)
    elif stage_hint == "formed":
        target_count = max(target_count, 20)
    state["manifest"]["interaction_count"] = max(int(state["manifest"].get("interaction_count", 0)), target_count)
    update_stage(state)

    plasticity = _coerce_unit(maturity.get("plasticity", 0.35), 0.35)
    state["learning"]["event_lr"] = round(0.025 + plasticity * 0.055, 5)
    state["learning"]["teaching_lr"] = round(0.035 + plasticity * 0.070, 5)

    imported_prototypes = _backup_prototypes(backup)
    if imported_prototypes:
        if merge:
            state["situation_prototypes"] = (imported_prototypes + state.get("situation_prototypes", []))[
                : int(state["learning"]["prototype_limit"])
            ]
        else:
            state["situation_prototypes"] = imported_prototypes[: int(state["learning"]["prototype_limit"])]

    deltas = _latent_deltas(before, snapshot_latent(state))
    appraisal = appraise("mature old agent personality backup import")
    trace = make_trace(
        state,
        "mature_import",
        backup_text,
        appraisal,
        None,
        "restored",
        deltas,
        "Imported a mature PIL backup. Raw old conversations remain outside the runtime personality layer.",
    )
    append_trace(state, trace)
    return state


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PKM v1 personality kernel prototype")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE, help="PKM state path")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="create a fresh PKM state")
    p_init.add_argument("--force", action="store_true")

    p_teach = sub.add_parser("teach", help="owner teaching; updates personality disposition")
    p_teach.add_argument("text")

    p_decide = sub.add_parser("decide", help="appraise an event and arbitrate behavior")
    p_decide.add_argument("text")

    p_settle = sub.add_parser("settle", help="settle a task outcome and update PKM")
    p_settle.add_argument("text")
    p_settle.add_argument("--outcome", required=True, choices=["success", "failure", "mixed"])
    p_settle.add_argument("--note", default="")

    sub.add_parser("show", help="show visible summary")

    p_export = sub.add_parser("export-visible", help="export 3D visible morphology JSON")
    p_export.add_argument("--out", type=Path, default=DEFAULT_VISIBLE)

    p_handoff = sub.add_parser("export-handoff", help="export a fresh Codex dialogue test packet")
    p_handoff.add_argument("--out", type=Path, default=ROOT / "NEW_CODEX_TEST.md")
    p_handoff.add_argument("--mode", choices=["fresh", "continue"], default="fresh")
    p_handoff.add_argument("--lang", choices=["auto", "zh", "en"], default="auto")

    p_import = sub.add_parser("import-backup", help="import a mature PIL personality backup into PKM state")
    p_import.add_argument("backup", type=Path)
    p_import.add_argument("--out-visible", type=Path, default=DEFAULT_VISIBLE)
    p_import.add_argument("--merge", action="store_true", help="merge over existing state instead of replacing it")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "init":
        init_state(args.state, force=args.force)
        print(f"created PKM state: {args.state}")
        return 0

    if args.command == "import-backup":
        backup = load_personality_backup(args.backup)
        if args.merge and args.state.exists():
            state = load_state(args.state)
        else:
            state = default_state()
        apply_personality_backup(state, backup, merge=args.merge)
        save_state(args.state, state)
        visible = export_visible(state, args.out_visible)
        print_json(
            {
                "imported": str(args.backup),
                "state": str(args.state),
                "visible": str(args.out_visible),
                "agent": state["manifest"],
                "visible_agent": visible["agent"],
                "next": "Run pkm_runtime.py boot --mode continue or launch_personality_observatory.ps1 to see the mature personality ball.",
            }
        )
        return 0

    state = load_state(args.state)

    if args.command == "teach":
        result = teach(state, args.text)
        save_state(args.state, state)
        print_json(result)
        return 0

    if args.command == "decide":
        print_json(decide(state, args.text))
        return 0

    if args.command == "settle":
        result = settle(state, args.text, args.outcome, args.note)
        save_state(args.state, state)
        print_json(result)
        return 0

    if args.command == "show":
        print_json(
            {
                "agent": state["manifest"],
                "visible": visible_summary(state),
                "latest_growth": state.get("growth_trace", [])[-1:] or None,
                "prototype_count": len(state.get("situation_prototypes", [])),
            }
        )
        return 0

    if args.command == "export-visible":
        visible = export_visible(state, args.out)
        print_json({"exported": str(args.out), "agent": visible["agent"]})
        return 0

    if args.command == "export-handoff":
        export_handoff(state, args.out, args.mode, args.lang)
        print_json({"exported": str(args.out), "agent": state["manifest"]})
        return 0

    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
