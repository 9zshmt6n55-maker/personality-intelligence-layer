#!/usr/bin/env python3
from __future__ import annotations

import argparse
import colorsys
import json
import locale
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageTk
import tkinter as tk


ROOT = Path(__file__).resolve().parent
DEFAULT_VISIBLE = ROOT / "public" / "pkm_visible.json"
SIGNAL_FILE = ROOT / "state" / "orb_signal.json"
READY_FILE = ROOT / "state" / "orb_ready.json"
TRANSPARENT_KEY = "#cafff0"


@dataclass
class Vec:
    x: float
    y: float
    z: float


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def add(a: Vec, b: Vec) -> Vec:
    return Vec(a.x + b.x, a.y + b.y, a.z + b.z)


def mul(a: Vec, s: float) -> Vec:
    return Vec(a.x * s, a.y * s, a.z * s)


def dot(a: Vec, b: Vec) -> float:
    return a.x * b.x + a.y * b.y + a.z * b.z


def cross(a: Vec, b: Vec) -> Vec:
    return Vec(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x)


def normalize(point: Vec) -> Vec:
    length = math.sqrt(point.x * point.x + point.y * point.y + point.z * point.z) or 1.0
    return Vec(point.x / length, point.y / length, point.z / length)


def direction_from_angles(theta: float, phi: float) -> Vec:
    return normalize(
        Vec(
            math.sin(phi) * math.cos(theta),
            math.cos(phi),
            math.sin(phi) * math.sin(theta),
        )
    )


def direction(item: dict[str, Any]) -> Vec:
    if "_dir" in item:
        return item["_dir"]
    if item.get("direction"):
        x, y, z = item["direction"]
        return normalize(Vec(float(x), float(y), float(z)))
    return direction_from_angles(float(item["theta"]), float(item["phi"]))


def tangent_basis(dir_vec: Vec) -> tuple[Vec, Vec]:
    up = Vec(1, 0, 0) if abs(dir_vec.y) > 0.86 else Vec(0, 1, 0)
    t1 = normalize(cross(up, dir_vec))
    t2 = normalize(cross(dir_vec, t1))
    return t1, t2


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    raw = hex_color.lstrip("#")
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def mix_rgb(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        round(a[0] * (1 - t) + b[0] * t),
        round(a[1] * (1 - t) + b[1] * t),
        round(a[2] * (1 - t) + b[2] * t),
    )


def brighten(rgb: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return mix_rgb(rgb, (252, 255, 238), amount)


def spectrum_rgb(phase: float, bias: float, saturation: float = 0.86, value: float = 1.0) -> tuple[int, int, int]:
    hue = (bias / math.tau + phase * 0.018) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
    return round(r * 255), round(g * 255), round(b * 255)


def dynamic_rgb(base_hex: str, phase: float, bias: float) -> tuple[int, int, int]:
    base = mix_rgb(hex_to_rgb(base_hex), spectrum_rgb(phase, bias, 0.88, 0.98), 0.66)
    teal = (18, 220, 212)
    amber = (246, 178, 42)
    rose = (232, 58, 142)
    violet = (104, 72, 238)
    t1 = (math.sin(phase * 0.44 + bias) + 1) * 0.5
    t2 = (math.sin(phase * 0.30 + bias * 1.6) + 1) * 0.5
    t3 = (math.sin(phase * 0.23 + bias * 0.7) + 1) * 0.5
    chroma = mix_rgb(mix_rgb(base, teal, 0.24 * t1), mix_rgb(amber, rose, t2), 0.18)
    return brighten(mix_rgb(chroma, violet, 0.14 * t3), 0.015)


UI_TEXT = {
    "zh": {
        "title": "人格体",
        "subtitle": "桌面观察台",
        "stage": "阶段",
        "count": "次数",
        "type": "类型",
        "force": "当前合力",
        "dominant": "主导域",
        "confidence": "自信形态",
        "maturity": "成熟度",
        "differentiation": "分化度",
        "entropy": "熵",
        "strength": "强度",
        "growth": "成长痕迹",
        "decision": "当前决策",
        "no_growth": "暂无成长痕迹。新代理仍是低分化圆形人格体。",
        "changed": "变化",
        "settings": "设置",
        "labels": "标签",
        "topmost": "置顶",
        "collapse": "收起",
        "quit": "关闭",
        "domain": "域",
        "action": "行动",
        "area": "面积",
        "height": "高度",
        "stability": "稳定",
        "tension": "张力",
        "facets": "细分",
        "thinking": "思考中",
        "idle": "运行中",
        "hint": "拖动球体旋转，悬停查看域。",
        "open": "打开观察台",
        "compact": "宠物模式",
        "unknown": "未知",
    },
    "en": {
        "title": "Personality Body",
        "subtitle": "desktop observatory",
        "stage": "Stage",
        "count": "Count",
        "type": "Type",
        "force": "Resultant Force",
        "dominant": "Dominant Domain",
        "confidence": "Confidence Form",
        "maturity": "Maturity",
        "differentiation": "Differentiation",
        "entropy": "Entropy",
        "strength": "Strength",
        "growth": "Growth Trace",
        "decision": "Decision",
        "no_growth": "No growth trace yet. The new agent is still a low-differentiation sphere.",
        "changed": "Changed",
        "settings": "Settings",
        "labels": "Labels",
        "topmost": "Topmost",
        "collapse": "Collapse",
        "quit": "Quit",
        "domain": "Domain",
        "action": "Action",
        "area": "Area",
        "height": "Height",
        "stability": "Stability",
        "tension": "Tension",
        "facets": "Facets",
        "thinking": "Thinking",
        "idle": "Running",
        "hint": "Drag the sphere to rotate; hover to inspect domains.",
        "open": "Open observatory",
        "compact": "pet mode",
        "unknown": "unknown",
    },
}


def detect_ui_language() -> str:
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


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    names = ["msyhbd.ttc", "simhei.ttf", "msyh.ttc", "seguisb.ttf", "segoeui.ttf"] if bold else [
        "msyh.ttc",
        "simhei.ttf",
        "segoeui.ttf",
        "arial.ttf",
    ]
    for name in names:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def draw_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
) -> None:
    draw.text(xy, text, font=font, fill=fill)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text).splitlines() or [""]:
        current = ""
        for char in paragraph:
            candidate = current + char
            if current and text_size(draw, candidate, font)[0] > max_width:
                lines.append(current)
                current = char
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines or [""]


def fit_text(draw: ImageDraw.ImageDraw, text: Any, font: ImageFont.ImageFont, max_width: int) -> str:
    value = str(text or "")
    if text_size(draw, value, font)[0] <= max_width:
        return value
    ellipsis = "..."
    result = value
    while result and text_size(draw, result + ellipsis, font)[0] > max_width:
        result = result[:-1]
    return (result + ellipsis) if result else ellipsis


def pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except Exception:
        return "0%"


def metric(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except Exception:
        return "0.00"


@dataclass
class Ripple:
    direction: Vec
    started: float
    strength: float = 0.86


@dataclass
class Wobble:
    started: float
    strength: float = 1.0


class OrbRenderer:
    def __init__(self, data: dict[str, Any], size: int = 112) -> None:
        self.data = data
        self.size = size
        self.center = size / 2
        self.yaw = -0.55
        self.pitch = 0.12
        self.roll = 0.0
        self.active_anchors = self._active_anchor_map(data)
        self.regions = self._hydrate_regions(data.get("model", {}).get("regions", []))
        self.confidence = self._hydrate_modes(data.get("model", {}).get("confidence_modes", []))
        dynamics = data.get("model", {}).get("dynamics", {})
        maturity = float(dynamics.get("maturity", 0.0))
        differentiation = float(dynamics.get("differentiation", 0.0))
        self.formation = clamp(maturity * 1.65 + differentiation * 1.35)
        self.cells = self._build_cells()
        self.ripples: list[Ripple] = []
        self.wobbles: list[Wobble] = []
        self.thinking = False
        self._current_wobble = 0.0
        self._mask_cache: dict[tuple[int, int, int, int], Image.Image] = {}

    def _active_anchor_map(self, data: dict[str, Any]) -> dict[str, float]:
        active: dict[str, float] = {}

        def add_growth(trace: dict[str, Any], weight: float) -> None:
            for item in trace.get("visible_delta") or []:
                anchor = str(item.get("anchor", ""))
                if not anchor:
                    continue
                try:
                    delta = abs(float(item.get("delta", 0.0)))
                except Exception:
                    delta = 0.0
                active[anchor] = max(active.get(anchor, 0.0), clamp(delta * 8.0 * weight))

        latest = data.get("latest_growth") or {}
        if latest:
            add_growth(latest, 1.0)
        recent = data.get("recent_growth") or []
        for age, trace in enumerate(reversed(recent[-4:]), start=1):
            add_growth(trace, max(0.18, 0.55 / age))
        runtime = data.get("runtime") or {}
        active_decision = runtime.get("active_decision") or {}
        try:
            decision_intensity = clamp(float(active_decision.get("intensity", 0.0)))
        except Exception:
            decision_intensity = 0.0
        winner = str(active_decision.get("winner", ""))
        if winner:
            active[winner] = max(active.get(winner, 0.0), decision_intensity)
        for domain in active_decision.get("active_domains") or []:
            region_id = str(domain.get("id", ""))
            action = str(domain.get("action", ""))
            try:
                activation = clamp(float(domain.get("activation", 0.0)) * max(0.55, decision_intensity))
            except Exception:
                activation = decision_intensity
            if region_id:
                active[region_id] = max(active.get(region_id, 0.0), activation)
            if action:
                active[action] = max(active.get(action, 0.0), activation * 0.78)
        return active

    def _region_activity_boost(self, region: dict[str, Any]) -> float:
        region_id = str(region.get("id", ""))
        action = str(region.get("action", ""))
        links = {
            "directness": {"direct", "conclusion_first", "direct_action"},
            "objectivity": {"objective_filter", "verify", "verify_first"},
            "risk_sensitivity": {"verify", "refuse", "small_step", "verify_first"},
            "trust": {"support", "ask_owner", "deescalate"},
            "boundary": {"boundary", "refuse", "assertive_boundary"},
            "self_control": {"boundary", "deescalate", "assertive_boundary"},
            "curiosity": {"explore", "small_step"},
            "craft": {"small_step", "direct"},
            "empathy": {"support", "deescalate"},
            "autonomy": {"ask_owner", "explore"},
        }
        boost = self.active_anchors.get(region_id, 0.0) + self.active_anchors.get(action, 0.0)
        for anchor, targets in links.items():
            if region_id in targets or action in targets:
                boost += self.active_anchors.get(anchor, 0.0)
        return clamp(boost)

    def _hydrate_regions(self, regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        hydrated = []
        for region in regions[:26]:
            next_region = dict(region)
            next_region["_dir"] = direction(next_region)
            next_region["_basis"] = tangent_basis(next_region["_dir"])
            next_region["_field_strength"] = float(region.get("height", 0)) * (0.62 + float(region.get("area", 0)) * 4.1)
            next_region["_phase"] = float(region.get("theta", 0)) * 1.93
            next_region["_activity_boost"] = self._region_activity_boost(next_region)
            hydrated.append(next_region)
        return hydrated

    def _hydrate_modes(self, modes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        hydrated = []
        for mode in modes:
            next_mode = dict(mode)
            next_mode["_dir"] = direction(next_mode)
            next_mode["_basis"] = tangent_basis(next_mode["_dir"])
            next_mode["_field_strength"] = float(mode.get("height", 0)) * 0.24
            next_mode["_phase"] = float(mode.get("theta", 0))
            hydrated.append(next_mode)
        return hydrated

    def _nearest_region(self, dir_vec: Vec) -> dict[str, Any] | None:
        best = None
        best_score = -999.0
        for region in self.regions:
            score = dot(dir_vec, region["_dir"])
            if score > best_score:
                best = region
                best_score = score
        return best

    def _build_cells(self) -> list[dict[str, Any]]:
        substrate = self.data.get("model", {}).get("substrate", {})
        density = float(substrate.get("density", 0.68))
        count = min(int(substrate.get("seed_count", 112)), 42)
        golden_angle = math.pi * (3 - math.sqrt(5))
        cells = []
        for i in range(count):
            y = 1 - ((i + 0.5) / count) * 2
            ring = math.sqrt(max(0.0, 1 - y * y))
            theta = i * golden_angle
            dir_vec = normalize(Vec(math.cos(theta) * ring, y, math.sin(theta) * ring))
            owner = self._nearest_region(dir_vec)
            t1, t2 = tangent_basis(dir_vec)
            owner_strength = (float(owner.get("value", 0.5)) * 0.14 + float(owner.get("area", 0.04)) * 2.2) if owner else 0.18
            cells.append(
                {
                    "_dir": dir_vec,
                    "_basis": (t1, t2),
                    "color": owner.get("color", "#6d877f") if owner else "#6d877f",
                    "phase": theta + i * 0.17,
                    "size": 0.072 + density * 0.050 + owner_strength * 0.022,
                    "alpha": 0.010 + density * 0.012 + owner_strength * 0.004,
                }
            )
        return cells

    def rotate(self, point: Vec) -> Vec:
        cy = math.cos(self.yaw)
        sy = math.sin(self.yaw)
        cp = math.cos(self.pitch)
        sp = math.sin(self.pitch)
        cr = math.cos(self.roll)
        sr = math.sin(self.roll)
        x1 = point.x * cy - point.z * sy
        z1 = point.x * sy + point.z * cy
        y1 = point.y * cp - z1 * sp
        z2 = point.y * sp + z1 * cp
        x2 = x1 * cr - y1 * sr
        y2 = x1 * sr + y1 * cr
        return Vec(x2, y2, z2)

    def inverse_rotate(self, point: Vec) -> Vec:
        cr = math.cos(-self.roll)
        sr = math.sin(-self.roll)
        cp = math.cos(-self.pitch)
        sp = math.sin(-self.pitch)
        cy = math.cos(-self.yaw)
        sy = math.sin(-self.yaw)
        x1 = point.x * cr - point.y * sr
        y1 = point.x * sr + point.y * cr
        y2 = y1 * cp - point.z * sp
        z1 = y1 * sp + point.z * cp
        x2 = x1 * cy - z1 * sy
        z2 = x1 * sy + z1 * cy
        return normalize(Vec(x2, y2, z2))

    def project(self, point: Vec) -> tuple[float, float, float]:
        rotated = self.rotate(point)
        distance = 4.08
        scale = self.size * 1.42 / (distance - rotated.z)
        wobble = self._current_wobble
        scale_x = 1.0 + wobble * 0.34
        scale_y = 1.0 - wobble * 0.27
        return self.center + rotated.x * scale * scale_x, self.center - rotated.y * scale * scale_y, rotated.z

    def _wobble_bbox(self, radius: float, phase_shift: float = 0.0) -> tuple[float, float, float, float]:
        wobble = self._current_wobble + math.sin(phase_shift) * 0.025
        scale_x = 1.0 + wobble * 0.24
        scale_y = 1.0 - wobble * 0.20
        return (
            self.center - radius * scale_x,
            self.center - radius * scale_y,
            self.center + radius * scale_x,
            self.center + radius * scale_y,
        )

    def _body_mask(self, radius: float, blur: float, scale: int = 1) -> Image.Image:
        wobble_key = int(round(self._current_wobble * 1000))
        key = (int(round(radius * 100)), int(round(blur * 100)), max(1, scale), wobble_key)
        cached = self._mask_cache.get(key)
        if cached is not None:
            return cached
        if len(self._mask_cache) > 48:
            self._mask_cache.clear()
        mask = Image.new("L", (self.size * scale, self.size * scale), 0)
        mask_draw = ImageDraw.Draw(mask)
        bbox = tuple(value * scale for value in self._wobble_bbox(radius))
        mask_draw.ellipse(bbox, fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=max(0.8, blur * scale)))
        if scale != 1:
            mask = mask.resize((self.size, self.size), Image.Resampling.LANCZOS)
        self._mask_cache[key] = mask
        return mask

    def _clip_to_body(self, image: Image.Image) -> None:
        mask = self._body_mask(self.size * 0.431, max(1.2, self.size * 0.0035), scale=3)
        image.putalpha(ImageChops.multiply(image.getchannel("A"), mask))

    def set_thinking(self, thinking: bool) -> None:
        self.thinking = thinking

    def kick(self, phase: float, strength: float = 1.0) -> None:
        self.wobbles.append(Wobble(phase, strength))
        self.wobbles = self.wobbles[-6:]

    def wobble_amount(self, phase: float) -> float:
        amount = 0.0
        active = []
        for wobble in self.wobbles:
            age = phase - wobble.started
            if age > 2.1:
                continue
            active.append(wobble)
            amount += math.sin(age * 18.5) * math.exp(-age * 1.95) * 0.23 * wobble.strength
        self.wobbles = active
        return clamp(amount, -0.72, 0.72)

    def ripple_field(self, dir_vec: Vec, phase: float) -> float:
        amount = 0.0
        active = []
        for ripple in self.ripples:
            age = phase - ripple.started
            if age > 2.8:
                continue
            active.append(ripple)
            angle = math.acos(clamp(dot(dir_vec, ripple.direction), -1, 1))
            front = age * 0.58
            band = math.exp(-((angle - front) ** 2) / 0.0065)
            center_pull = math.exp(-(angle**2) / 0.020) * math.exp(-age * 2.2)
            wave = math.sin((angle - age * 0.54) * 36) * band
            amount += ripple.strength * (wave * math.exp(-age * 0.82) - center_pull * 0.15)
        self.ripples = active
        return amount

    def personality_field(self, dir_vec: Vec, phase: float) -> float:
        amount = 0.0
        for region in self.regions:
            influence = max(0.0, dot(dir_vec, region["_dir"])) ** 8.1
            breathing = 1 + math.sin(phase * 0.62 + region["_phase"]) * 0.035
            amount += influence * region["_field_strength"] * breathing
        for mode in self.confidence:
            influence = max(0.0, dot(dir_vec, mode["_dir"])) ** 12
            amount += influence * mode["_field_strength"] * (1 + math.sin(phase * 0.84 + mode["_phase"]) * 0.025)
        return amount * (0.20 + self.formation * 0.80) + self.ripple_field(dir_vec, phase)

    def surface_point(self, dir_vec: Vec, radius: float, phase: float) -> Vec:
        subtle = (
            math.sin(dir_vec.x * 5.2 + phase * 0.50) * 0.007
            + math.sin(dir_vec.z * 6.4 - phase * 0.38) * 0.006
            + math.sin((dir_vec.x + dir_vec.y) * 7.3 + phase * 0.27) * 0.005
        )
        return mul(dir_vec, radius + self.personality_field(dir_vec, phase) * 0.24 + subtle)

    def click_direction(self, x: float, y: float) -> Vec | None:
        radius = self.size * 0.43
        nx = (x - self.center) / radius
        ny = (self.center - y) / radius
        d2 = nx * nx + ny * ny
        if d2 > 1.08:
            return None
        z = math.sqrt(max(0.02, 1 - min(d2, 1)))
        return self.inverse_rotate(Vec(nx, ny, z))

    def add_ripple(self, x: float, y: float, phase: float) -> None:
        dir_vec = self.click_direction(x, y)
        if not dir_vec:
            return
        self.ripples.append(Ripple(dir_vec, phase))
        self.kick(phase, 1.42)
        self.ripples = self.ripples[-6:]

    def region_at(self, x: float, y: float, min_score: float = 0.48) -> dict[str, Any] | None:
        if self.formation < 0.12:
            return None
        dir_vec = self.click_direction(x, y)
        if not dir_vec:
            return None
        best = None
        best_score = -999.0
        for region in self.regions:
            score = dot(dir_vec, region["_dir"])
            if score > best_score:
                best = region
                best_score = score
        if best and best_score >= min_score:
            result = dict(best)
            result["_score"] = best_score
            return result
        return None

    def _polygon_points(self, points: list[Vec]) -> list[tuple[float, float]]:
        return [(x, y) for x, y, _ in (self.project(point) for point in points)]

    def _draw_radial_glow(
        self,
        image: Image.Image,
        center: tuple[float, float],
        radius: float,
        color: tuple[int, int, int],
        max_alpha: int,
        steps: int = 44,
    ) -> None:
        pad = max(18, int(self.size * 0.10))
        layer = Image.new("RGBA", (self.size + pad * 2, self.size + pad * 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer, "RGBA")
        cx, cy = center
        for i in range(steps, 0, -1):
            t = i / steps
            alpha = round(max_alpha * (1 - t) ** 1.8)
            r = radius * t
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*color, alpha))
        image.alpha_composite(layer)

    def _cell_polygon(self, cell: dict[str, Any], phase: float) -> list[Vec]:
        t1, t2 = cell["_basis"]
        points = []
        size = float(cell["size"]) * (1 + math.sin(phase * 0.36 + float(cell["phase"])) * 0.09)
        for i in range(12):
            a = (math.pi * 2 * i) / 12
            wobble = 1 + math.sin(a * 3 + float(cell["phase"]) + phase * 0.13) * 0.14
            angular = size * wobble
            dir_vec = normalize(
                add(
                    mul(cell["_dir"], math.cos(angular)),
                    add(mul(t1, math.cos(a) * math.sin(angular)), mul(t2, math.sin(a) * math.sin(angular))),
                )
            )
            points.append(self.surface_point(dir_vec, 1.04, phase))
        return points

    def _patch_polygon(self, item: dict[str, Any], phase: float, scale: float = 1.0) -> list[Vec]:
        dir_vec = item["_dir"]
        t1, t2 = item["_basis"]
        area_radius = (0.13 + math.sqrt(float(item.get("area", 0.05))) * 0.70) * scale
        roughness = float(item.get("roughness", 0.2))
        points = []
        for i in range(42):
            a = (math.pi * 2 * i) / 42
            wobble = (
                1
                + math.sin(a * 3 + float(item.get("theta", 0)) * 1.5 + phase * 0.21) * roughness * 0.12
                + math.sin(a * 7 + float(item.get("phi", 0)) * 2.4 - phase * 0.17) * roughness * 0.07
            )
            angular = area_radius * wobble
            rim = normalize(
                add(
                    mul(dir_vec, math.cos(angular)),
                    add(mul(t1, math.cos(a) * math.sin(angular)), mul(t2, math.sin(a) * math.sin(angular))),
                )
            )
            points.append(self.surface_point(rim, 1.14 + max(float(item.get("height", 0)), -0.10) * 0.20, phase))
        return points

    def _accent_patches(self, phase: float) -> list[dict[str, Any]]:
        # Synthetic color patches made the desktop version feel cheaper than
        # the original web morphology. Region and confidence fields should
        # carry the mature surface instead.
        return []

    def _draw_curve_path(
        self,
        draw: ImageDraw.ImageDraw,
        points: list[Vec],
        color: tuple[int, int, int],
        alpha: int,
    ) -> None:
        if len(points) < 2 or alpha <= 0:
            return
        projected = [self.project(point)[:2] for point in points]
        draw.line(projected, fill=(*color, alpha), width=1)

    def _draw_layer_lattice(self, draw: ImageDraw.ImageDraw, phase: float) -> None:
        # The latitude/longitude lattice looked acceptable in offscreen previews
        # but turns into a dark wireframe on some Windows/remote-host transparent
        # window compositors. It is not part of the finalized personality-ball
        # language, so keep the mature sphere glassy instead of gridded.
        return
        if self.formation < 0.82:
            return
        intensity = clamp((self.formation - 0.82) / 0.16)
        layers = self.data.get("model", {}).get("layers", [])
        if not layers:
            return
        lat_steps = 7 if self.size >= 220 else 5
        long_steps = 9 if self.size >= 220 else 6
        theta_steps = 64 if self.size >= 220 else 42
        phi_steps = 58 if self.size >= 220 else 38
        for index, layer in enumerate(layers):
            try:
                radius = float(layer.get("radius", 1.0))
                color = hex_to_rgb(str(layer.get("color", "#6d877f")))
            except Exception:
                continue
            base_alpha = int((1.5 + index * 1.2) * intensity)
            if base_alpha <= 0:
                continue
            for row in range(1, lat_steps):
                phi = 0.18 + (math.pi - 0.36) * row / lat_steps
                points = []
                for step in range(theta_steps + 1):
                    theta = math.tau * step / theta_steps
                    dir_vec = direction_from_angles(theta, phi)
                    points.append(self.surface_point(dir_vec, radius, phase))
                self._draw_curve_path(draw, points, brighten(color, 0.14), base_alpha)
            for col in range(long_steps):
                theta = math.tau * col / long_steps + math.sin(phase * 0.13 + col) * 0.010
                points = []
                for step in range(phi_steps + 1):
                    phi = 0.12 + (math.pi - 0.24) * step / phi_steps
                    dir_vec = direction_from_angles(theta, phi)
                    points.append(self.surface_point(dir_vec, radius, phase))
                self._draw_curve_path(draw, points, brighten(color, 0.10), max(1, base_alpha - 1))

    def _draw_cut_plane(self, image: Image.Image, phase: float) -> None:
        if self.formation < 0.20:
            return
        layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer, "RGBA")
        cx = self.center + math.sin(phase * 0.23) * self.size * 0.034 + math.sin(phase * 0.071) * self.size * 0.014
        cy = self.center + self.size * (0.045 + math.cos(phase * 0.17) * 0.024)
        angle = -21.5 + math.sin(phase * 0.13) * 6.4 + math.sin(phase * 0.29) * 2.8
        breath = (math.sin(phase * 0.37) + 1.0) * 0.5
        width = self.size * (0.086 + self.formation * 0.036 + math.sin(phase * 0.31) * 0.010)
        height = self.size * (0.610 + self.formation * 0.070 + math.cos(phase * 0.19) * 0.030)
        lobes = [
            (0.00, 0.00, 1.00, 1.00, (238, 228, 194), 1.00),
            (-0.18, -0.18, 0.70, 0.45, (214, 226, 196), 0.58),
            (0.14, 0.23, 0.58, 0.40, (174, 210, 205), 0.42),
        ]
        for dx, dy, sx, sy, rgb, power in lobes:
            drift_x = math.sin(phase * (0.41 + sx * 0.11) + dy * 3.7) * self.size * 0.012
            drift_y = math.cos(phase * (0.33 + sy * 0.09) + dx * 2.9) * self.size * 0.010
            lcx = cx + dx * width + drift_x
            lcy = cy + dy * height * 0.22 + drift_y
            for i in range(24, 0, -1):
                t = i / 24
                alpha = int((1 - t) ** 1.62 * (34 + self.formation * 25 + breath * 16) * power)
                w = width * sx * t
                h = height * sy * t
                draw.ellipse((lcx - w, lcy - h, lcx + w, lcy + h), fill=(*rgb, alpha))
        line_count = 11 if self.size >= 240 else 7
        for j in range(line_count):
            seed = j * 1.618
            span = height * (0.46 + 0.10 * math.sin(seed))
            x0 = cx + math.sin(phase * 0.42 + seed) * width * 0.45
            y0 = cy - span * 0.5 + math.cos(phase * 0.24 + seed) * self.size * 0.014
            points: list[tuple[float, float]] = []
            for step in range(22):
                u = step / 21
                wave = math.sin(u * math.tau * (1.35 + (j % 3) * 0.18) + phase * 0.72 + seed)
                taper = math.sin(math.pi * u)
                points.append(
                    (
                        x0 + wave * width * (0.30 + 0.10 * math.sin(seed * 0.7)) * taper,
                        y0 + span * u + math.sin(phase * 0.19 + u * 4.2 + seed) * self.size * 0.010,
                    )
                )
            alpha = int(9 + breath * 8 + (j % 3) * 2)
            draw.line(points, fill=(255, 244, 206, alpha), width=1)
        layer = layer.filter(ImageFilter.GaussianBlur(radius=max(1.2, self.size * 0.0042)))
        layer = layer.rotate(angle, center=(cx, cy), resample=Image.Resampling.BICUBIC)
        _, _, mask = self._masked_layer(self.size * 0.421)
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
        image.alpha_composite(layer)

    def _draw_embryo_potential(self, image: Image.Image, phase: float, thinking_pulse: float) -> None:
        if self.formation >= 0.12:
            return
        layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer, "RGBA")
        golden_angle = math.pi * (3 - math.sqrt(5))
        count = 18
        for i in range(count):
            y = 1 - ((i + 0.5) / count) * 2
            ring = math.sqrt(max(0.0, 1 - y * y))
            theta = i * golden_angle + phase * 0.022
            dir_vec = normalize(Vec(math.cos(theta) * ring * 0.78, y * 0.78, math.sin(theta) * ring * 0.78))
            projected = self.project(dir_vec)
            if projected[2] < -0.18:
                continue
            pulse = (math.sin(phase * 0.55 + i * 1.73) + 1) * 0.5
            radius = self.size * (0.0055 + pulse * 0.0035)
            alpha = int(8 + pulse * 12 + max(projected[2], 0.0) * 7 + thinking_pulse * 7)
            color = mix_rgb((190, 252, 243), (242, 255, 231), pulse * 0.26)
            px, py = projected[0], projected[1]
            draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=(*color, alpha))
        layer = layer.filter(ImageFilter.GaussianBlur(radius=max(2, self.size // 95)))
        image.alpha_composite(layer)

    def _masked_layer(self, radius: float | None = None) -> tuple[Image.Image, ImageDraw.ImageDraw, Image.Image]:
        layer = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer, "RGBA")
        mask = self._body_mask(radius if radius is not None else self.size * 0.431, max(0.8, self.size * 0.0018), scale=1)
        return layer, draw, mask

    def _soft_ellipse_blob(
        self,
        image: Image.Image,
        center: tuple[float, float],
        radii: tuple[float, float],
        color: tuple[int, int, int],
        alpha: int,
        blur: float,
        rotation: float = 0.0,
    ) -> None:
        if alpha <= 0:
            return
        cx, cy = center
        rx, ry = max(1.0, radii[0]), max(1.0, radii[1])
        extent = math.hypot(rx, ry) if abs(rotation) > 0.001 else max(rx, ry)
        margin = int(math.ceil(max(4.0, blur * 3.1, self.size * 0.018)))
        left = max(0, int(math.floor(cx - extent - margin)))
        top = max(0, int(math.floor(cy - extent - margin)))
        right = min(self.size, int(math.ceil(cx + extent + margin)))
        bottom = min(self.size, int(math.ceil(cy + extent + margin)))
        if right <= left or bottom <= top:
            return
        layer = Image.new("RGBA", (right - left, bottom - top), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer, "RGBA")
        local_cx = cx - left
        local_cy = cy - top
        draw.ellipse((local_cx - rx, local_cy - ry, local_cx + rx, local_cy + ry), fill=(*color, alpha))
        if abs(rotation) > 0.001:
            layer = layer.rotate(rotation, center=(local_cx, local_cy), resample=Image.Resampling.BICUBIC)
        layer = layer.filter(ImageFilter.GaussianBlur(radius=blur))
        image.alpha_composite(layer, (left, top))

    def _embryo_blob(
        self,
        image: Image.Image,
        center: tuple[float, float],
        radius: float,
        color: tuple[int, int, int],
        alpha: int,
        blur: float,
    ) -> None:
        self._soft_ellipse_blob(image, center, (radius, radius), color, alpha, blur)

    def _embryo_ellipse_blob(
        self,
        image: Image.Image,
        center: tuple[float, float],
        radii: tuple[float, float],
        color: tuple[int, int, int],
        alpha: int,
        blur: float,
        rotation: float = 0.0,
    ) -> None:
        self._soft_ellipse_blob(image, center, radii, color, alpha, blur, rotation)

    def _draw_embryo_strands(self, image: Image.Image, phase: float) -> None:
        layer, draw, mask = self._masked_layer(self.size * 0.410)
        count = 132 if self.size >= 240 else 62
        palette = [
            (238, 229, 186),
            (188, 222, 224),
            (214, 152, 138),
            (198, 190, 232),
            (176, 217, 177),
            (226, 210, 168),
        ]
        for i in range(count):
            base = i * 1.618 + phase * 0.145
            rx = self.size * (0.075 + (i % 9) * 0.018)
            ry = self.size * (0.024 + (i % 11) * 0.006)
            cx = self.center + math.sin(base * 1.7) * self.size * 0.20
            cy = self.center + math.cos(base * 1.3) * self.size * 0.17
            color = palette[i % len(palette)]
            alpha = 6 + (i % 6) * 2
            points = []
            rotation = base * 0.48
            cr = math.cos(rotation)
            sr = math.sin(rotation)
            for step in range(52):
                a = math.tau * step / 51
                wobble = 1 + math.sin(a * 3 + base) * 0.07
                x = math.cos(a) * rx * wobble
                y = math.sin(a) * ry * (1 + math.cos(a * 2 + base) * 0.08)
                points.append((cx + x * cr - y * sr, cy + x * sr + y * cr))
            draw.line(points, fill=(*color, alpha), width=1)
        for i in range(32 if self.size >= 240 else 16):
            a0 = phase * 0.125 + i * 0.71
            points = []
            for step in range(90):
                t = step / 89
                a = a0 + t * math.tau * (0.58 + (i % 4) * 0.11)
                r = self.size * (0.10 + t * 0.24 + math.sin(t * math.pi + i) * 0.015)
                x = self.center + math.cos(a) * r + math.sin(t * 8 + i) * self.size * 0.018
                y = self.center + math.sin(a) * r * 0.78 + math.cos(t * 7 + i) * self.size * 0.014
                points.append((x, y))
            color = palette[(i + 2) % len(palette)]
            draw.line(points, fill=(*color, 9), width=1)
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
        image.alpha_composite(layer)

    def _draw_embryo_surface_fibers(self, image: Image.Image, phase: float) -> None:
        layer, draw, mask = self._masked_layer(self.size * 0.408)
        palette = [
            (245, 238, 204),
            (202, 228, 224),
            (229, 178, 160),
            (195, 205, 238),
            (196, 225, 188),
        ]
        count = 66 if self.size >= 240 else 30
        for i in range(count):
            theta = phase * 0.135 + i * 0.53
            cx = self.center + math.cos(theta * 1.7) * self.size * (0.035 + (i % 5) * 0.020)
            cy = self.center + math.sin(theta * 1.3) * self.size * (0.026 + (i % 7) * 0.016)
            rx = self.size * (0.20 + (i % 7) * 0.024)
            ry = self.size * (0.074 + (i % 5) * 0.013)
            rot = theta * 0.62 + math.sin(i) * 0.25
            cr = math.cos(rot)
            sr = math.sin(rot)
            start = 0.18 + (i % 9) * 0.21
            span = 1.9 + (i % 5) * 0.28
            points = []
            for step in range(44):
                t = step / 43
                a = start + span * t
                wave = 1 + math.sin(a * 5.0 + theta) * 0.035
                x = math.cos(a) * rx * wave
                y = math.sin(a) * ry
                points.append((cx + x * cr - y * sr, cy + x * sr + y * cr))
            color = palette[i % len(palette)]
            alpha = 10 + (i % 5) * 3
            draw.line(points, fill=(*color, alpha), width=1)
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
        image.alpha_composite(layer)

    def _draw_embryo_geodesic_fibers(self, image: Image.Image, phase: float) -> None:
        layer, draw, mask = self._masked_layer(self.size * 0.406)
        palette = [
            (244, 237, 203),
            (203, 225, 224),
            (225, 181, 161),
            (194, 202, 236),
            (202, 224, 188),
            (233, 216, 168),
        ]
        count = 66 if self.size >= 240 else 30
        golden_angle = math.pi * (3 - math.sqrt(5))
        for i in range(count):
            y = 1 - ((i + 0.5) / count) * 2
            if abs(y) > 0.74:
                continue
            ring = math.sqrt(max(0.0, 1 - y * y))
            theta = i * golden_angle + phase * 0.095
            center_dir = normalize(Vec(math.cos(theta) * ring, y, math.sin(theta) * ring))
            projected_center = self.project(center_dir)
            if projected_center[2] < -0.34:
                continue
            t1, t2 = tangent_basis(center_dir)
            span = 0.20 + (i % 6) * 0.034
            curve = []
            for step in range(48):
                t = step / 47
                u = (t - 0.5) * span
                v = math.sin(t * math.tau * (1.30 + (i % 4) * 0.18) + phase * 0.32 + i) * span * 0.30
                curl = math.sin(t * math.pi * 1.6 + i * 0.31 + phase * 0.17) * span * 0.13
                dir_vec = normalize(add(center_dir, add(mul(t1, u + curl), mul(t2, v))))
                point = self.project(mul(dir_vec, 0.992 + math.sin(t * math.pi + phase * 0.45 + i) * 0.006))
                curve.append((point[0], point[1]))
            color = palette[i % len(palette)]
            alpha = int(3 + max(projected_center[2], 0.0) * 6 + (i % 4))
            draw.line(curve, fill=(*color, alpha), width=1)
        layer = layer.filter(ImageFilter.GaussianBlur(radius=max(0.15, self.size * 0.0008)))
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
        image.alpha_composite(layer)

    def _draw_embryo_core_filaments(self, image: Image.Image, phase: float) -> None:
        layer, draw, mask = self._masked_layer(self.size * 0.405)
        cx = self.center - self.size * 0.020
        cy = self.center - self.size * 0.030
        for i in range(46 if self.size >= 240 else 20):
            base = phase * 0.21 + i * 0.67
            color = mix_rgb((255, 244, 197), (232, 214, 150), (i % 5) / 5)
            points = []
            rx = self.size * (0.080 + (i % 8) * 0.015)
            ry = self.size * (0.026 + (i % 6) * 0.010)
            rot = base * 0.38 + math.sin(i * 0.7) * 0.72
            cr = math.cos(rot)
            sr = math.sin(rot)
            start = (i % 11) * 0.17
            span = math.tau * (0.42 + (i % 5) * 0.055)
            for step in range(46):
                t = step / 45
                a = start + span * t + math.sin(t * math.pi + i) * 0.040
                wobble = 1 + math.sin(a * 3.2 + base) * 0.035
                x = math.cos(a) * rx * wobble
                y = math.sin(a) * ry
                points.append((cx + x * cr - y * sr, cy + x * sr + y * cr))
            draw.line(points, fill=(*color, 5 + (i % 4) * 2), width=1)
        layer = layer.filter(ImageFilter.GaussianBlur(radius=max(0.45, self.size * 0.0015)))
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
        image.alpha_composite(layer)

    def _draw_embryo_color_whorls(self, image: Image.Image, phase: float) -> None:
        layer, draw, mask = self._masked_layer(self.size * 0.410)
        regions = [
            (-0.265, -0.060, 0.190, 0.122, -18, (229, 206, 74), 15, 11),
            (0.230, -0.220, 0.146, 0.112, 20, (218, 118, 112), 13, 9),
            (0.248, 0.238, 0.166, 0.124, -18, (85, 196, 188), 13, 9),
            (-0.298, 0.215, 0.130, 0.096, 17, (118, 142, 214), 11, 7),
            (-0.010, 0.270, 0.152, 0.084, 4, (164, 192, 118), 10, 6),
            (0.000, -0.315, 0.122, 0.080, 8, (184, 170, 226), 9, 6),
        ]
        for gx, gy, grx, gry, rotation_deg, color, alpha, count in regions:
            cx = self.center + self.size * gx
            cy = self.center + self.size * gy
            rot = math.radians(rotation_deg)
            cr = math.cos(rot)
            sr = math.sin(rot)
            for i in range(count):
                base = phase * 0.115 + i * 0.72 + gx * 2.1
                rx = self.size * grx * (0.46 + (i % 4) * 0.075)
                ry = self.size * gry * (0.42 + (i % 5) * 0.070)
                points = []
                start = (i % 7) * 0.28
                span = math.tau * (0.58 + (i % 4) * 0.080)
                for step in range(54):
                    t = step / 53
                    a = start + span * t
                    wobble = 1 + math.sin(a * 3.6 + base) * 0.055
                    x = math.cos(a) * rx * wobble + math.sin(t * math.tau + base) * self.size * grx * 0.030
                    y = math.sin(a) * ry * (1 + math.cos(a * 2.2 + base) * 0.045)
                    points.append((cx + x * cr - y * sr, cy + x * sr + y * cr))
                draw.line(points, fill=(*color, alpha + (i % 3) * 3), width=1)
        layer = layer.filter(ImageFilter.GaussianBlur(radius=max(0.18, self.size * 0.0009)))
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
        image.alpha_composite(layer)

    def _draw_embryo_grain(self, image: Image.Image, phase: float) -> None:
        layer, draw, mask = self._masked_layer(self.size * 0.414)
        count = 150 if self.size >= 240 else 64
        for i in range(count):
            a = i * 2.399963 + phase * 0.065
            r = math.sqrt((i + 0.5) / count) * self.size * 0.405
            x = self.center + math.cos(a) * r
            y = self.center + math.sin(a) * r * 0.96
            twinkle = (math.sin(phase * 0.7 + i * 1.31) + 1) * 0.5
            alpha = int(3 + twinkle * 6)
            radius = 0.30 + twinkle * 0.36
            color = mix_rgb((232, 230, 203), (190, 226, 222), (i % 7) / 7)
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*color, alpha))
        layer = layer.filter(ImageFilter.GaussianBlur(radius=0.48))
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
        image.alpha_composite(layer)

    def _draw_embryo_depth(self, image: Image.Image) -> None:
        layer = Image.new("RGBA", (self.size, self.size), (18, 28, 26, 0))
        ring = Image.new("L", (self.size, self.size), 0)
        ring_draw = ImageDraw.Draw(ring)
        ring_draw.ellipse(self._wobble_bbox(self.size * 0.430), fill=28)
        ring_draw.ellipse(self._wobble_bbox(self.size * 0.382), fill=0)
        ring = ring.filter(ImageFilter.GaussianBlur(radius=max(5, self.size * 0.014)))
        _, _, body_mask = self._masked_layer()
        layer.putalpha(ImageChops.multiply(ring, body_mask))
        image.alpha_composite(layer)

    def _render_embryo(self, phase: float, thinking_pulse: float, fast: bool = False) -> Image.Image:
        image = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        body, body_draw, mask = self._masked_layer()
        body_draw.ellipse(self._wobble_bbox(self.size * 0.431), fill=(74, 91, 87, 42 + round(thinking_pulse * 7)))
        body.putalpha(ImageChops.multiply(body.getchannel("A"), mask))
        image.alpha_composite(body)

        self._embryo_blob(
            image,
            (self.center, self.center),
            self.size * 0.47,
            (155, 179, 170),
            9,
            max(24, self.size * 0.090),
        )
        self._embryo_blob(
            image,
            (self.center - self.size * 0.030, self.center - self.size * 0.035),
            self.size * 0.220,
            (255, 239, 186),
            70 + round(thinking_pulse * 24),
            max(20, self.size * 0.064),
        )
        self._embryo_ellipse_blob(
            image,
            (self.center - self.size * 0.010, self.center - self.size * 0.030),
            (self.size * 0.136, self.size * 0.104),
            (255, 247, 211),
            66 + round(thinking_pulse * 26),
            max(12, self.size * 0.044),
            -7,
        )
        self._embryo_blob(
            image,
            (self.center + self.size * 0.020, self.center - self.size * 0.024),
            self.size * 0.070,
            (255, 250, 224),
            38 + round(thinking_pulse * 20),
            max(8, self.size * 0.032),
        )
        self._embryo_ellipse_blob(image, (self.center - self.size * 0.285, self.center - self.size * 0.055), (self.size * 0.215, self.size * 0.138), (218, 204, 70), 55, max(18, self.size * 0.068), -18)
        self._embryo_ellipse_blob(image, (self.center + self.size * 0.235, self.center - self.size * 0.218), (self.size * 0.162, self.size * 0.118), (210, 106, 102), 48, max(18, self.size * 0.064), 22)
        self._embryo_ellipse_blob(image, (self.center + self.size * 0.245, self.center + self.size * 0.238), (self.size * 0.184, self.size * 0.132), (72, 192, 186), 48, max(18, self.size * 0.070), -18)
        self._embryo_ellipse_blob(image, (self.center - self.size * 0.300, self.center + self.size * 0.232), (self.size * 0.142, self.size * 0.106), (112, 136, 210), 39, max(16, self.size * 0.058), 18)
        self._embryo_ellipse_blob(image, (self.center + self.size * 0.000, self.center - self.size * 0.320), (self.size * 0.138, self.size * 0.086), (184, 168, 226), 30, max(16, self.size * 0.058), 8)
        self._embryo_ellipse_blob(image, (self.center - self.size * 0.040, self.center + self.size * 0.268), (self.size * 0.158, self.size * 0.088), (166, 194, 116), 32, max(16, self.size * 0.056), 6)

        if fast:
            self._draw_embryo_color_whorls(image, phase)
            self._draw_embryo_core_filaments(image, phase)
        else:
            self._draw_embryo_strands(image, phase)
            self._draw_embryo_geodesic_fibers(image, phase)
            self._draw_embryo_surface_fibers(image, phase)
            self._draw_embryo_color_whorls(image, phase)
            self._draw_embryo_core_filaments(image, phase)
            self._draw_embryo_grain(image, phase)
        self._draw_embryo_depth(image)

        glint = Image.new("RGBA", image.size, (0, 0, 0, 0))
        glint_draw = ImageDraw.Draw(glint, "RGBA")
        cx = self.center - self.size * 0.15
        cy = self.center - self.size * 0.20
        glint_draw.ellipse(
            (cx - self.size * 0.105, cy - self.size * 0.045, cx + self.size * 0.105, cy + self.size * 0.045),
            fill=(255, 250, 218, 34),
        )
        glint = glint.filter(ImageFilter.GaussianBlur(radius=max(4, self.size * 0.018)))
        glint.putalpha(ImageChops.multiply(glint.getchannel("A"), mask))
        image.alpha_composite(glint)

        rim_scale = 3
        rim = Image.new("RGBA", (self.size * rim_scale, self.size * rim_scale), (0, 0, 0, 0))
        rim_draw = ImageDraw.Draw(rim, "RGBA")

        def scaled_bbox(bbox: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
            return tuple(round(value * rim_scale) for value in bbox)

        rim_draw.arc(
            scaled_bbox(self._wobble_bbox(self.size * 0.421)),
            start=132,
            end=188,
            fill=(238, 246, 226, 24),
            width=rim_scale,
        )
        rim = rim.resize(image.size, Image.Resampling.LANCZOS)
        image.alpha_composite(rim)

        self._clip_to_body(image)
        if self.thinking:
            pulse = Image.new("RGBA", image.size, (0, 0, 0, 0))
            pulse_draw = ImageDraw.Draw(pulse, "RGBA")
            pulse_draw.ellipse(
                self._wobble_bbox(self.size * (0.35 + thinking_pulse * 0.035), phase),
                outline=(255, 226, 140, 72 + round(thinking_pulse * 68)),
                width=1,
            )
            pulse = pulse.filter(ImageFilter.GaussianBlur(radius=max(2, self.size * 0.010)))
            image.alpha_composite(pulse)
        return image

    def _draw_surface_fibrils(self, draw: ImageDraw.ImageDraw, phase: float, thinking_pulse: float) -> None:
        if self.formation < 0.30:
            return
        if not self.thinking and not self.ripples:
            return
        intensity = clamp((self.formation - 0.30) / 0.58)
        count = max(6, int((24 if self.size >= 180 else 14) * intensity))
        golden_angle = math.pi * (3 - math.sqrt(5))
        for i in range(count):
            y = 1 - ((i + 0.5) / count) * 2
            ring = math.sqrt(max(0.0, 1 - y * y))
            theta = i * golden_angle + phase * 0.075
            dir_vec = normalize(Vec(math.cos(theta) * ring, y, math.sin(theta) * ring))
            projected = self.project(dir_vec)
            if projected[2] < -0.18:
                continue
            t1, t2 = tangent_basis(dir_vec)
            drift = math.sin(phase * 0.76 + i * 1.91)
            span = (0.022 + self.formation * 0.016) * intensity
            mid = normalize(add(dir_vec, add(mul(t1, span * 0.55), mul(t2, span * drift * 0.40))))
            end = normalize(add(dir_vec, add(mul(t1, span), mul(t2, span * drift))))
            points = [
                self.project(self.surface_point(dir_vec, 1.035, phase))[:2],
                self.project(self.surface_point(mid, 1.055, phase))[:2],
                self.project(self.surface_point(end, 1.035, phase))[:2],
            ]
            rgb = spectrum_rgb(phase, theta + i * 0.23, 0.34, 1.0)
            alpha = int((8 + max(projected[2], 0.0) * 24 + thinking_pulse * 8) * intensity)
            draw.line(points, fill=(*brighten(rgb, 0.36), alpha), width=1)

    def _draw_rim_prominences(self, image: Image.Image, phase: float, thinking_pulse: float, fast: bool = False) -> None:
        if self.formation < 0.42:
            return
        intensity = clamp((self.formation - 0.42) / 0.48)
        pad = max(18, int(self.size * 0.10))
        layer = Image.new("RGBA", (self.size + pad * 2, self.size + pad * 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer, "RGBA")
        center = self.center + pad
        candidates = []
        for index, region in enumerate(self.regions):
            rotated = self.rotate(region["_dir"])
            radial = math.hypot(rotated.x, rotated.y)
            if rotated.z < -0.20:
                continue
            visibility = clamp((rotated.z + 0.20) / 1.20)
            if visibility <= 0:
                continue
            edge_weight = clamp((radial - 0.44) / 0.48)
            area = float(region.get("area", 0.04))
            height = max(float(region.get("height", 0.0)), 0.0)
            tension = float(region.get("tension", 0.0))
            roughness = float(region.get("roughness", 0.0))
            recent_boost = float(region.get("_activity_boost", 0.0))
            phase_bias = float(region.get("_phase", index * 0.73))
            domain_power = clamp(area * 3.2 + height * 1.2 + tension * 0.42 + roughness * 0.30)
            frequency = (0.70 + domain_power * 0.52 + recent_boost * 1.35) * 0.50
            activity = (math.sin(phase * (0.36 + frequency * 0.17) + phase_bias) + 1) * 0.5
            exponent = max(1.35, 2.65 - recent_boost * 1.15 - domain_power * 0.40)
            burst = max(0.0, math.sin(phase * frequency + phase_bias * 1.37)) ** exponent
            trigger = burst + thinking_pulse * 0.55 + recent_boost * 0.72 + (0.28 if self.ripples else 0.0)
            score = visibility * domain_power * (0.38 + trigger + recent_boost * 0.55)
            threshold = 0.52 - recent_boost * 0.22 - domain_power * 0.08
            if trigger < threshold and score < 0.16:
                continue
            surface = self.project(self.surface_point(region["_dir"], 1.10 + height * 0.12, phase))
            candidates.append((score, index, region, rotated, visibility, edge_weight, surface, activity, burst, domain_power, recent_boost, roughness))

        active_count = sum(1 for region in self.regions if float(region.get("_activity_boost", 0.0)) > 0.20)
        limit = 1 + min(1, active_count) + (1 if self.thinking or self.ripples else 0)
        if fast:
            limit = 1
        for score, index, region, rotated, visibility, edge_weight, surface, activity, burst, domain_power, recent_boost, roughness in sorted(candidates, key=lambda item: item[0], reverse=True)[:limit]:
            base_x = surface[0] + pad
            base_y = surface[1] + pad
            out_x = base_x - center
            out_y = base_y - center
            out_len = math.hypot(out_x, out_y)
            if out_len < 1:
                out_x, out_y = math.cos(phase + index), math.sin(phase + index)
            else:
                out_x, out_y = out_x / out_len, out_y / out_len
            tangent = (-out_y, out_x)
            shape = 0.75 + roughness * 0.55 + recent_boost * 0.35 + (index % 3) * 0.10
            length = (
                self.size
                * (0.018 + domain_power * 0.028 + recent_boost * 0.050 + activity * 0.020 + burst * 0.060 + thinking_pulse * 0.020)
                * intensity
                * (0.48 + visibility * 0.34 + edge_weight * 0.48)
            )
            spread = self.size * (0.006 + domain_power * 0.009 + recent_boost * 0.008 + activity * 0.010) * intensity
            curl = math.sin(index * 1.7 + phase * (0.24 + recent_boost * 0.20)) * length * (0.20 + shape * 0.22)
            outward = length * (0.28 + edge_weight * 0.72)
            start = (
                base_x - tangent[0] * spread * 0.75 - out_x * length * 0.04,
                base_y - tangent[1] * spread * 0.75 - out_y * length * 0.04,
            )
            lift1 = (
                base_x + out_x * outward * (0.24 + shape * 0.08) + tangent[0] * (curl * 0.30 - spread * 0.35),
                base_y + out_y * outward * (0.24 + shape * 0.08) + tangent[1] * (curl * 0.30 - spread * 0.35),
            )
            apex = (
                base_x + out_x * outward + tangent[0] * curl,
                base_y + out_y * outward + tangent[1] * curl,
            )
            lift2 = (
                base_x + out_x * outward * (0.30 + shape * 0.08) + tangent[0] * (curl * (0.18 + shape * 0.10) + spread * 0.35),
                base_y + out_y * outward * (0.30 + shape * 0.08) + tangent[1] * (curl * (0.18 + shape * 0.10) + spread * 0.35),
            )
            end = (
                base_x + tangent[0] * spread * 0.75 - out_x * length * 0.02,
                base_y + tangent[1] * spread * 0.75 - out_y * length * 0.02,
            )
            rgb = dynamic_rgb(str(region.get("color", "#7aa097")), phase, float(region.get("theta", 0.0)))
            alpha = int((18 + domain_power * 42 + recent_boost * 78 + activity * 30 + burst * 74 + thinking_pulse * 42) * intensity * (0.58 + visibility * 0.28 + edge_weight * 0.34))
            draw.line([start, lift1, apex, lift2, end], fill=(*brighten(rgb, 0.50), alpha), width=1)
            if not fast and (burst > 0.66 or self.thinking):
                inner = (
                    base_x + out_x * outward * 0.54 + tangent[0] * curl * 0.45,
                    base_y + out_y * outward * 0.54 + tangent[1] * curl * 0.45,
                )
                draw.line([start, inner, end], fill=(*brighten(rgb, 0.70), max(14, alpha // 3)), width=1)
        image.alpha_composite(layer.crop((pad, pad, pad + self.size, pad + self.size)))

    def _render_fast_grown(self, phase: float, thinking_pulse: float, highlight_id: str | None) -> Image.Image:
        image = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image, "RGBA")
        draw.ellipse(self._wobble_bbox(self.size * 0.431), fill=(74, 92, 88, 92 + round(self.formation * 28)))
        draw.ellipse(
            (
                self.center - self.size * 0.245,
                self.center - self.size * 0.210,
                self.center + self.size * 0.170,
                self.center + self.size * 0.125,
            ),
            fill=(246, 232, 180, 34 + round(thinking_pulse * 16)),
        )
        clouds = [
            (-0.285, -0.055, 0.205, 0.130, (218, 204, 70), 34),
            (0.235, -0.218, 0.162, 0.118, (210, 106, 102), 26),
            (0.245, 0.238, 0.184, 0.132, (72, 192, 186), 28),
            (-0.300, 0.232, 0.142, 0.106, (112, 136, 210), 22),
        ]
        for gx, gy, rx, ry, rgb, alpha in clouds:
            cx = self.center + self.size * gx
            cy = self.center + self.size * gy
            draw.ellipse((cx - self.size * rx, cy - self.size * ry, cx + self.size * rx, cy + self.size * ry), fill=(*rgb, alpha))
        if self.size >= 180:
            self._draw_embryo_color_whorls(image, phase)

        active_regions = sorted(self.regions, key=lambda item: float(item.get("area", 0)), reverse=True)[:7]
        region_depths = [(self.project(region["_dir"])[2], region) for region in active_regions]
        for depth, region in sorted(region_depths, key=lambda item: item[0]):
            if depth < -0.06:
                continue
            rgb = dynamic_rgb(str(region.get("color", "#6d877f")), phase, float(region.get("theta", 0)))
            rgb = mix_rgb(brighten(rgb, 0.36), (238, 229, 194), 0.12)
            highlighted = bool(highlight_id and region.get("id") == highlight_id)
            alpha = int(
                255
                * clamp(
                    0.020
                    + float(region.get("area", 0)) * 0.34
                    + max(float(region.get("height", 0)), 0) * 0.040
                    + (0.08 if highlighted else 0.0),
                    0.025,
                    0.24,
                )
            )
            polygon = self._polygon_points(self._patch_polygon(region, phase, 0.78))
            draw.polygon(polygon, fill=(*rgb, alpha), outline=(*brighten(rgb, 0.14), min(40, alpha // 4)))
        return image

    def render(self, phase: float, auto_spin: bool = True, highlight_id: str | None = None, fast: bool = False) -> Image.Image:
        if auto_spin:
            self.yaw += 0.0075
            self.pitch = clamp(self.pitch + math.sin(phase * 0.24) * 0.0007, -0.82, 0.82)
        self.roll = math.sin(phase * 0.18) * 0.035
        self._current_wobble = self.wobble_amount(phase)
        thinking_pulse = (math.sin(phase * 8.2) + 1) * 0.5 if self.thinking else 0.0
        if self.formation < 0.12:
            return self._render_embryo(phase, thinking_pulse, fast=fast)
        if fast:
            return self._render_fast_grown(phase, thinking_pulse, highlight_id)

        image = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        body, body_draw, mask = self._masked_layer()
        body_alpha = 48 + round(self.formation * 34) + round(thinking_pulse * 7)
        body_draw.ellipse(self._wobble_bbox(self.size * 0.431), fill=(76, 94, 90, body_alpha))
        body.putalpha(ImageChops.multiply(body.getchannel("A"), mask))
        image.alpha_composite(body)

        core_dx = math.sin(phase * 0.18) * self.size * 0.016 + math.sin(phase * 0.051) * self.size * 0.010
        core_dy = math.cos(phase * 0.15) * self.size * 0.014
        core_breath = math.sin(phase * 0.34) * self.size * 0.007
        self._embryo_blob(image, (self.center + core_dx * 0.32, self.center + core_dy * 0.24), self.size * 0.47, (150, 174, 166), 9 + round(self.formation * 8), max(24, self.size * 0.090))
        self._embryo_blob(image, (self.center - self.size * 0.030 + core_dx, self.center - self.size * 0.035 + core_dy), self.size * 0.220 + core_breath, (255, 239, 186), 58 + round(thinking_pulse * 22), max(20, self.size * 0.066))
        self._embryo_ellipse_blob(image, (self.center - self.size * 0.285, self.center - self.size * 0.055), (self.size * 0.215, self.size * 0.138), (218, 204, 70), 42, max(18, self.size * 0.068), -18)
        self._embryo_ellipse_blob(image, (self.center + self.size * 0.235, self.center - self.size * 0.218), (self.size * 0.162, self.size * 0.118), (210, 106, 102), 38, max(18, self.size * 0.064), 22)
        self._embryo_ellipse_blob(image, (self.center + self.size * 0.245, self.center + self.size * 0.238), (self.size * 0.184, self.size * 0.132), (72, 192, 186), 38, max(18, self.size * 0.070), -18)
        self._embryo_ellipse_blob(image, (self.center - self.size * 0.300, self.center + self.size * 0.232), (self.size * 0.142, self.size * 0.106), (112, 136, 210), 30, max(16, self.size * 0.058), 18)
        self._embryo_ellipse_blob(image, (self.center + self.size * 0.000, self.center - self.size * 0.320), (self.size * 0.138, self.size * 0.086), (184, 168, 226), 24, max(16, self.size * 0.058), 8)
        if fast:
            self._draw_embryo_color_whorls(image, phase)
        else:
            self._draw_embryo_strands(image, phase)
            self._draw_embryo_geodesic_fibers(image, phase)
            self._draw_embryo_color_whorls(image, phase)

        region_layer, region_draw, region_mask = self._masked_layer(self.size * 0.423)
        active_cells = self.cells[::3] if fast else self.cells
        cell_depths = [(self.project(cell["_dir"])[2], cell) for cell in active_cells]
        for depth, cell in sorted(cell_depths, key=lambda item: item[0]):
            if depth < -0.25:
                continue
            rgb = dynamic_rgb(str(cell["color"]), phase, float(cell["phase"]))
            rgb = mix_rgb(brighten(rgb, 0.38), (232, 228, 202), 0.12)
            alpha = int(255 * clamp(float(cell["alpha"]) * (1.7 + self.formation * 2.5 + thinking_pulse * 0.50), 0.014, 0.125))
            polygon = self._polygon_points(self._cell_polygon(cell, phase))
            region_draw.polygon(polygon, fill=(*rgb, alpha), outline=(*brighten(rgb, 0.16), min(12, max(2, int(alpha * 0.08)))))

        active_regions = sorted(self.regions, key=lambda item: float(item.get("area", 0)), reverse=True)[:10] if fast else self.regions
        region_depths = [(self.project(region["_dir"])[2], region) for region in active_regions]
        for depth, region in sorted(region_depths, key=lambda item: item[0]):
            if depth < -0.12:
                continue
            rgb = dynamic_rgb(str(region.get("color", "#6d877f")), phase, float(region.get("theta", 0)))
            rgb = mix_rgb(brighten(rgb, 0.44), (238, 229, 194), 0.10)
            highlighted = bool(highlight_id and region.get("id") == highlight_id)
            alpha = int(
                255
                * clamp(
                    (0.014 + self.formation * 0.058)
                    + float(region.get("area", 0)) * (0.24 + self.formation * 0.46)
                    + max(float(region.get("height", 0)), 0) * 0.052
                    + max(depth, 0) * 0.012
                    + thinking_pulse * 0.012
                    + (0.11 if highlighted else 0.0),
                    0.024,
                    0.320,
                )
            )
            polygon = self._polygon_points(self._patch_polygon(region, phase, 0.92))
            region_draw.polygon(
                polygon,
                fill=(*rgb, alpha),
                outline=(*brighten(rgb, 0.22 if highlighted else 0.14), min(66, int(alpha * (0.42 if highlighted else 0.13)))),
            )
        region_layer = region_layer.filter(ImageFilter.GaussianBlur(radius=max(0.35, self.size * 0.0018)))
        region_layer.putalpha(ImageChops.multiply(region_layer.getchannel("A"), region_mask))
        image.alpha_composite(region_layer)

        draw = ImageDraw.Draw(image, "RGBA")
        if not fast:
            self._draw_layer_lattice(draw, phase)
            self._draw_surface_fibrils(draw, phase, thinking_pulse)

        glint = Image.new("RGBA", image.size, (255, 251, 224, 0))
        glint_draw = ImageDraw.Draw(glint, "RGBA")
        cx = self.center - self.size * 0.12 + math.sin(phase * 0.25) * self.size * 0.02
        cy = self.center - self.size * 0.18
        glint_draw.ellipse(
            (
                cx - self.size * 0.105,
                cy - self.size * 0.060,
                cx + self.size * 0.105,
                cy + self.size * 0.060,
            ),
            fill=(255, 238, 176, 40 + round(thinking_pulse * 22)),
        )
        glint = glint.filter(ImageFilter.GaussianBlur(radius=max(3, self.size // 90)))
        image.alpha_composite(glint)
        self._draw_cut_plane(image, phase)
        self._clip_to_body(image)
        self._draw_rim_prominences(image, phase, thinking_pulse, fast=fast)
        if self.thinking:
            pulse_radius = self.size * (0.34 + thinking_pulse * 0.10)
            pulse = Image.new("RGBA", image.size, (255, 255, 232, 0))
            pulse_draw = ImageDraw.Draw(pulse, "RGBA")
            pulse_draw.ellipse(
                self._wobble_bbox(pulse_radius, phase),
                fill=(250, 184, 68, 10 + round(thinking_pulse * 18)),
                outline=(255, 224, 104, 88 + round(thinking_pulse * 92)),
                width=1,
            )
            pulse = pulse.filter(ImageFilter.GaussianBlur(radius=max(4, self.size // 28)))
            image.alpha_composite(pulse)
        return image


class DesktopOrb:
    def __init__(
        self,
        data: dict[str, Any],
        size: int,
        opacity: float,
        visible_path: Path,
        signal_path: Path = SIGNAL_FILE,
        initial_x: int | None = None,
        initial_y: int | None = None,
    ) -> None:
        self.data = data
        self.compact_size = size
        self.console_orb_size = max(260, min(340, size * 3))
        self.min_size = 72
        self.max_size = 520
        self.mode = "compact"
        self.opacity = opacity
        self.visible_path = visible_path
        self.visible_mtime = visible_path.stat().st_mtime if visible_path.exists() else 0.0
        self.lang = detect_ui_language()
        self.text = UI_TEXT[self.lang]
        self.font_title = load_font(28, True)
        self.font_subtitle = load_font(12, True)
        self.font_body = load_font(13)
        self.font_small = load_font(11)
        self.font_micro = load_font(10)
        self.font_button = load_font(12, True)
        self.renderer = OrbRenderer(data, size=size)
        self._glow_cache: dict[tuple[int, tuple[int, int, int], int], Image.Image] = {}
        self.topmost = True
        self.show_labels = False
        self.button_zones: list[tuple[str, tuple[int, int, int, int]]] = []
        self.hovered_region: dict[str, Any] | None = None
        self.selected_region: dict[str, Any] | None = None
        self.orb_rect = (0, 0, size, size)
        self.pointer_x = -999
        self.pointer_y = -999
        self.down_root_x = 0
        self.down_root_y = 0
        self.down_canvas_x = 0
        self.down_canvas_y = 0
        self.last_canvas_x = 0
        self.last_canvas_y = 0
        self.start_root_x = 0
        self.start_root_y = 0
        self.drag_mode: str | None = None
        self.pressed_button: str | None = None
        self.moved = False
        self.phase_start = time.perf_counter()
        self.last_drag_kick = 0.0
        self.last_signal_check = 0.0
        self.last_visible_check = 0.0
        self.signal_path = signal_path
        self.key_rgb = hex_to_rgb(TRANSPARENT_KEY)
        self.console_w = 820
        self.console_h = 456

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.configure(bg=TRANSPARENT_KEY)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 1.0)
        try:
            self.root.attributes("-transparentcolor", TRANSPARENT_KEY)
        except tk.TclError:
            pass

        self.canvas = tk.Canvas(
            self.root,
            width=size,
            height=size,
            highlightthickness=0,
            bd=0,
            bg=TRANSPARENT_KEY,
        )
        self.canvas.pack(fill="both", expand=True)
        self.image_id = self.canvas.create_image(0, 0, image=None, anchor="nw")
        self.tk_image: ImageTk.PhotoImage | None = None

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = initial_x if initial_x is not None else screen_w - size - 70
        y = initial_y if initial_y is not None else screen_h - size - 110
        x = int(clamp(x, 0, max(0, screen_w - size)))
        y = int(clamp(y, 0, max(0, screen_h - size)))
        self.root.geometry(f"{size}x{size}+{x}+{y}")

        self.tooltip = tk.Toplevel(self.root)
        self.tooltip.withdraw()
        self.tooltip.overrideredirect(True)
        self.tooltip.attributes("-topmost", True)
        self.tooltip.configure(bg="#071211")
        self.tooltip_label = tk.Label(
            self.tooltip,
            bg="#071211",
            fg="#eafff8",
            padx=9,
            pady=5,
            bd=0,
            font=("Microsoft YaHei UI", 9),
            justify="left",
        )
        self.tooltip_label.pack()

        self.canvas.bind("<Motion>", self.on_move)
        self.canvas.bind("<Leave>", self.on_leave)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-2>", self.on_middle_click)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.root.bind("<Escape>", lambda _event: self.set_mode("compact") if self.mode == "console" else self.root.destroy())

        self.menu = tk.Menu(self.root, tearoff=0)
        self.rebuild_menu()

    def rebuild_menu(self) -> None:
        self.menu.delete(0, "end")
        if self.mode == "compact":
            self.menu.add_command(label=self.text["open"], command=lambda: self.set_mode("console"))
        else:
            self.menu.add_command(label=self.text["collapse"], command=lambda: self.set_mode("compact"))
        self.menu.add_command(label=self.text["labels"], command=self.toggle_labels)
        self.menu.add_command(label=self.text["topmost"], command=self.toggle_topmost)
        self.menu.add_separator()
        self.menu.add_command(label=self.text["quit"], command=self.root.destroy)

    def renderer_size(self) -> int:
        return self.compact_size if self.mode == "compact" else self.console_orb_size

    def clone_renderer(self, size: int) -> None:
        old = self.renderer
        new_renderer = OrbRenderer(self.data, size=size)
        new_renderer.yaw = old.yaw
        new_renderer.pitch = old.pitch
        new_renderer.roll = old.roll
        new_renderer.thinking = old.thinking
        new_renderer.ripples = old.ripples
        new_renderer.wobbles = old.wobbles
        self.renderer = new_renderer

    def set_window_geometry(self, width: int, height: int, x: int, y: int) -> None:
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.canvas.configure(width=width, height=height)
        self.root.configure(bg=TRANSPARENT_KEY)
        self.canvas.configure(bg=TRANSPARENT_KEY)

    def present_image(self, image: Image.Image) -> None:
        desktop_image = Image.new("RGB", image.size, self.key_rgb)
        glass_matte = Image.new("RGBA", image.size, (54, 78, 74, 255))
        display_image = image.copy()
        boosted_alpha = image.getchannel("A").point(lambda value: min(255, round(value * 2.15)))
        display_image.putalpha(boosted_alpha)
        glass_rgb = Image.alpha_composite(glass_matte, display_image).convert("RGB")
        body_mask = image.getchannel("A").point(lambda value: 255 if value > 30 else 0)
        desktop_image.paste(glass_rgb, (0, 0), body_mask)
        self.tk_image = ImageTk.PhotoImage(desktop_image)
        self.canvas.itemconfigure(self.image_id, image=self.tk_image)

    def redraw_now(self, phase: float | None = None) -> None:
        phase = time.perf_counter() - self.phase_start if phase is None else phase
        image = self.draw_console(phase) if self.mode == "console" else self.draw_compact(phase)
        self.present_image(image)
        self.root.update_idletasks()

    def set_mode(self, mode: str) -> None:
        if mode == self.mode:
            return
        old_w = self.root.winfo_width() or self.renderer_size()
        old_h = self.root.winfo_height() or self.renderer_size()
        center_x = self.root.winfo_x() + old_w // 2
        center_y = self.root.winfo_y() + old_h // 2
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.mode = mode
        if mode == "console":
            self.clone_renderer(self.console_orb_size)
            x = int(clamp(center_x - self.console_w // 2, 16, max(16, screen_w - self.console_w - 16)))
            y = int(clamp(center_y - self.console_h // 2, 16, max(16, screen_h - self.console_h - 56)))
            self.set_window_geometry(self.console_w, self.console_h, x, y)
            self.hide_tooltip()
        else:
            self.clone_renderer(self.compact_size)
            x = int(clamp(center_x - self.compact_size // 2, 0, max(0, screen_w - self.compact_size)))
            y = int(clamp(center_y - self.compact_size // 2, 0, max(0, screen_h - self.compact_size)))
            self.set_window_geometry(self.compact_size, self.compact_size, x, y)
        self.rebuild_menu()
        self.renderer.kick(time.perf_counter() - self.phase_start, 0.72)

    def toggle_labels(self) -> None:
        self.show_labels = not self.show_labels

    def toggle_topmost(self) -> None:
        self.topmost = not self.topmost
        self.root.attributes("-topmost", self.topmost)
        try:
            self.tooltip.attributes("-topmost", self.topmost)
        except tk.TclError:
            pass

    def resize_orb(self, new_size: int, anchor_center: bool = True) -> None:
        if self.mode == "console":
            new_size = int(clamp(new_size, 220, 380))
            if new_size == self.console_orb_size:
                return
            self.console_orb_size = new_size
            self.clone_renderer(new_size)
        else:
            new_size = int(clamp(new_size, self.min_size, self.max_size))
            if new_size == self.compact_size:
                return
            old_size = self.compact_size
            old_x = self.root.winfo_x()
            old_y = self.root.winfo_y()
            center_x = old_x + old_size // 2
            center_y = old_y + old_size // 2
            self.compact_size = new_size
            self.clone_renderer(new_size)
            x = center_x - new_size // 2 if anchor_center else old_x
            y = center_y - new_size // 2 if anchor_center else old_y
            self.set_window_geometry(new_size, new_size, x, y)
        phase = time.perf_counter() - self.phase_start
        self.renderer.kick(phase, 0.72)
        self.redraw_now(phase)

    def on_middle_click(self, _event: tk.Event) -> None:
        self.set_mode("console" if self.mode == "compact" else "compact")

    def on_mouse_wheel(self, event: tk.Event) -> None:
        step = 22 if int(event.delta) > 0 else -22
        self.resize_orb(self.renderer_size() + step)

    def point_in_orb(self, x: int, y: int) -> bool:
        return self.local_orb_point(x, y) is not None

    def local_orb_point(self, x: int, y: int) -> tuple[float, float] | None:
        if self.mode == "compact":
            local = (float(x), float(y))
            return local if self.renderer.click_direction(local[0], local[1]) else None
        left, top, right, bottom = self.orb_rect
        if not (left <= x <= right and top <= y <= bottom):
            return None
        local = (float(x - left), float(y - top))
        return local if self.renderer.click_direction(local[0], local[1]) else None

    def button_at(self, x: int, y: int) -> str | None:
        for action, (left, top, right, bottom) in self.button_zones:
            if left <= x <= right and top <= y <= bottom:
                return action
        return None

    def on_move(self, event: tk.Event) -> None:
        self.pointer_x = int(event.x)
        self.pointer_y = int(event.y)
        if not self.drag_mode:
            self.update_hover(int(event.x_root), int(event.y_root))

    def on_leave(self, _event: tk.Event) -> None:
        self.pointer_x = -999
        self.pointer_y = -999
        self.hovered_region = None
        self.hide_tooltip()

    def on_press(self, event: tk.Event) -> None:
        self.down_root_x = int(event.x_root)
        self.down_root_y = int(event.y_root)
        self.down_canvas_x = int(event.x)
        self.down_canvas_y = int(event.y)
        self.last_canvas_x = int(event.x)
        self.last_canvas_y = int(event.y)
        self.start_root_x = self.root.winfo_x()
        self.start_root_y = self.root.winfo_y()
        self.moved = False
        self.pressed_button = self.button_at(int(event.x), int(event.y)) if self.mode == "console" else None
        if self.pressed_button:
            self.drag_mode = None
            return
        if self.mode == "compact":
            self.drag_mode = "window"
            return
        local = self.local_orb_point(int(event.x), int(event.y))
        shift_pressed = bool(int(event.state) & 0x0001)
        if local and not shift_pressed:
            self.drag_mode = "rotate"
            self.last_canvas_x = int(local[0])
            self.last_canvas_y = int(local[1])
            self.hovered_region = None
            self.hide_tooltip()
        else:
            self.drag_mode = "window"
            self.hovered_region = None
            self.hide_tooltip()

    def on_motion(self, event: tk.Event) -> None:
        dx_root = int(event.x_root) - self.down_root_x
        dy_root = int(event.y_root) - self.down_root_y
        if math.hypot(dx_root, dy_root) > 5:
            self.moved = True
        if self.drag_mode == "rotate":
            left, top, _, _ = self.orb_rect
            current_x = int(event.x) - left
            current_y = int(event.y) - top
            dx = current_x - self.last_canvas_x
            dy = current_y - self.last_canvas_y
            self.renderer.yaw += dx * 0.012
            self.renderer.pitch = clamp(self.renderer.pitch - dy * 0.010, -0.82, 0.82)
            self.last_canvas_x = current_x
            self.last_canvas_y = current_y
            self.hovered_region = None
            self.hide_tooltip()
            return
        if self.drag_mode == "window" and self.moved:
            self.root.geometry(f"+{self.start_root_x + dx_root}+{self.start_root_y + dy_root}")
            phase = time.perf_counter() - self.phase_start
            if phase - self.last_drag_kick > 0.14:
                self.renderer.kick(phase, min(1.30, 0.42 + math.hypot(dx_root, dy_root) / 90))
                self.last_drag_kick = phase
            self.hovered_region = None
            self.hide_tooltip()

    def on_release(self, event: tk.Event) -> None:
        phase = time.perf_counter() - self.phase_start
        if self.pressed_button and not self.moved:
            action = self.button_at(int(event.x), int(event.y))
            if action == self.pressed_button:
                self.execute_button(action)
            self.pressed_button = None
            self.drag_mode = None
            return
        local = self.local_orb_point(int(event.x), int(event.y))
        if local and not self.moved:
            self.renderer.add_ripple(local[0], local[1], phase)
            self.selected_region = self.hovered_region
        elif self.drag_mode in {"rotate", "window"} and self.moved:
            self.renderer.kick(phase, 1.28 if self.drag_mode == "window" else 0.65)
        self.drag_mode = None
        self.pressed_button = None
        self.update_hover(int(event.x_root), int(event.y_root))

    def execute_button(self, action: str) -> None:
        if action == "collapse":
            self.set_mode("compact")
        elif action == "labels":
            self.toggle_labels()
        elif action == "topmost":
            self.toggle_topmost()
        elif action == "quit":
            self.root.destroy()

    def on_right_click(self, event: tk.Event) -> None:
        self.rebuild_menu()
        self.menu.tk_popup(int(event.x_root), int(event.y_root))

    def update_hover(self, root_x: int | None = None, root_y: int | None = None) -> None:
        local = self.local_orb_point(self.pointer_x, self.pointer_y)
        self.hovered_region = self.renderer.region_at(local[0], local[1]) if local else None
        if self.mode == "compact" and self.hovered_region:
            label = str(self.hovered_region.get("label", self.text["unknown"]))
            area = pct(self.hovered_region.get("area", 0))
            height = metric(self.hovered_region.get("height", 0))
            self.tooltip_label.configure(text=f"{self.text['domain']}: {label}\n{self.text['area']}: {area}  {self.text['height']}: {height}")
            x = root_x if root_x is not None else self.root.winfo_pointerx()
            y = root_y if root_y is not None else self.root.winfo_pointery()
            self.tooltip.geometry(f"+{x + 14}+{y + 14}")
            self.tooltip.deiconify()
        else:
            self.hide_tooltip()

    def hide_tooltip(self) -> None:
        try:
            self.tooltip.withdraw()
        except tk.TclError:
            pass

    def read_signal(self, phase: float) -> None:
        if phase - self.last_signal_check < 0.25:
            return
        self.last_signal_check = phase
        try:
            payload = json.loads(self.signal_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.renderer.set_thinking(False)
            return
        except Exception:
            return
        thinking = bool(payload.get("thinking", False))
        if thinking and not self.renderer.thinking:
            self.renderer.kick(phase, 0.72)
        self.renderer.set_thinking(thinking)

    def reload_visible_if_changed(self, phase: float) -> None:
        if phase - self.last_visible_check < 0.80:
            return
        self.last_visible_check = phase
        try:
            mtime = self.visible_path.stat().st_mtime
        except FileNotFoundError:
            return
        if mtime <= self.visible_mtime:
            return
        try:
            data = load_data(self.visible_path)
        except Exception:
            return
        self.data = data
        self.clone_renderer(self.renderer_size())
        self.visible_mtime = mtime
        self.renderer.kick(phase, 0.95)

    def add_soft_glow(
        self,
        image: Image.Image,
        center: tuple[float, float],
        radius: float,
        color: tuple[int, int, int],
        alpha: int,
    ) -> None:
        if alpha <= 0:
            return
        blur = max(18, int(radius * 0.33))
        radius_key = int(round(radius))
        key = (radius_key, color, int(alpha))
        patch = self._glow_cache.get(key)
        if patch is None:
            if len(self._glow_cache) > 80:
                self._glow_cache.clear()
            half = int(math.ceil(radius_key + blur * 3.0))
            patch = Image.new("RGBA", (half * 2, half * 2), (0, 0, 0, 0))
            draw = ImageDraw.Draw(patch, "RGBA")
            draw.ellipse((half - radius, half - radius, half + radius, half + radius), fill=(*color, alpha))
            patch = patch.filter(ImageFilter.GaussianBlur(radius=blur))
            self._glow_cache[key] = patch
        cx, cy = center
        left = int(round(cx - patch.size[0] / 2))
        top = int(round(cy - patch.size[1] / 2))
        src_left = max(0, -left)
        src_top = max(0, -top)
        src_right = min(patch.size[0], image.size[0] - left)
        src_bottom = min(patch.size[1], image.size[1] - top)
        if src_right <= src_left or src_bottom <= src_top:
            return
        image.alpha_composite(patch.crop((src_left, src_top, src_right, src_bottom)), (left + src_left, top + src_top))

    def draw_button(
        self,
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        label: str,
        action: str,
        active: bool = False,
    ) -> None:
        self.button_zones.append((action, box))
        fill = (22, 39, 42, 236) if active else (12, 24, 26, 218)
        outline = (106, 240, 218, 160) if active else (124, 196, 188, 90)
        draw.rounded_rectangle(box, radius=12, fill=fill, outline=outline, width=1)
        w, h = text_size(draw, label, self.font_button)
        x = box[0] + (box[2] - box[0] - w) / 2
        y = box[1] + (box[3] - box[1] - h) / 2 - 1
        draw.text((x, y), label, font=self.font_button, fill=(226, 255, 248, 238))

    def draw_progress(
        self,
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        w: int,
        label: str,
        value: Any,
        color: tuple[int, int, int],
    ) -> int:
        try:
            number = clamp(float(value))
        except Exception:
            number = 0.0
        draw.text((x, y), label, font=self.font_small, fill=(178, 209, 202, 220))
        draw.text((x + w - 42, y), pct(number), font=self.font_small, fill=(230, 255, 246, 235))
        bar_y = y + 20
        draw.rounded_rectangle((x, bar_y, x + w, bar_y + 7), radius=4, fill=(31, 47, 48, 220))
        draw.rounded_rectangle((x, bar_y, x + max(8, int(w * number)), bar_y + 7), radius=4, fill=(*color, 220))
        return y + 38

    def draw_domain_label(self, draw: ImageDraw.ImageDraw, region: dict[str, Any], offset: tuple[int, int]) -> None:
        height = max(float(region.get("height", 0)), -0.10)
        p = self.renderer.project(mul(region["_dir"], 1.40 + height * 0.16))
        if p[2] < -0.72:
            return
        label = str(region.get("label", self.text["unknown"]))
        x = int(offset[0] + p[0])
        y = int(offset[1] + p[1])
        w, h = text_size(draw, label, self.font_micro)
        box = (x - w // 2 - 7, y - h // 2 - 4, x + w // 2 + 7, y + h // 2 + 5)
        draw.rounded_rectangle(box, radius=7, fill=(5, 13, 14, 210), outline=(*hex_to_rgb(str(region.get("color", "#67e1cf"))), 130))
        draw.text((box[0] + 7, box[1] + 3), label, font=self.font_micro, fill=(232, 255, 246, 238))

    def draw_hover_card(self, draw: ImageDraw.ImageDraw, region: dict[str, Any], mouse: tuple[int, int]) -> None:
        card_w = 270
        x = min(max(mouse[0] + 18, 22), self.console_w - card_w - 20)
        y = min(max(mouse[1] + 18, 62), self.console_h - 168)
        box = (x, y, x + card_w, y + 150)
        color = hex_to_rgb(str(region.get("color", "#67e1cf")))
        draw.rounded_rectangle(box, radius=18, fill=(5, 13, 15, 238), outline=(*brighten(color, 0.18), 160), width=1)
        draw.ellipse((x + 14, y + 15, x + 28, y + 29), fill=(*color, 230))
        draw.text((x + 36, y + 12), str(region.get("label", self.text["unknown"])), font=self.font_subtitle, fill=(235, 255, 248, 245))
        draw.text((x + 36, y + 32), str(region.get("action_label", "")), font=self.font_micro, fill=(166, 204, 198, 220))
        metrics = [
            (self.text["area"], pct(region.get("area", 0))),
            (self.text["height"], metric(region.get("height", 0))),
            (self.text["stability"], pct(region.get("stability", 0))),
            (self.text["tension"], pct(region.get("tension", 0))),
        ]
        mx, my = x + 16, y + 60
        for index, (name, value) in enumerate(metrics):
            dx = 0 if index % 2 == 0 else 130
            dy = 0 if index < 2 else 30
            draw.text((mx + dx, my + dy), name, font=self.font_micro, fill=(150, 182, 177, 220))
            draw.text((mx + dx + 48, my + dy), value, font=self.font_small, fill=(235, 255, 247, 235))
        facets = [str(item.get("label", "")) for item in (region.get("facets") or [])[:3] if item.get("label")]
        if facets:
            draw.text((x + 16, y + 122), f"{self.text['facets']}: {' / '.join(facets)}", font=self.font_micro, fill=(207, 236, 229, 230))

    def draw_analysis_panel(self, image: Image.Image, draw: ImageDraw.ImageDraw, phase: float) -> None:
        tx = self.text
        agent = self.data.get("agent", {})
        model = self.data.get("model", {})
        dynamics = model.get("dynamics", {})
        dominant = model.get("dominant_region") or {}
        confidence = model.get("dominant_confidence") or {}
        runtime_decision = (self.data.get("runtime") or {}).get("active_decision") or {}
        latest = self.data.get("latest_growth") or {}
        panel = (404, 78, 792, 424)
        draw.rounded_rectangle(panel, radius=24, fill=(5, 13, 15, 222), outline=(127, 242, 222, 72), width=1)
        self.add_soft_glow(image, (panel[2] - 56, panel[1] + 48), 84, (112, 72, 238), 28)
        self.add_soft_glow(image, (panel[0] + 80, panel[3] - 36), 92, (235, 155, 42), 22)

        x = panel[0] + 22
        y = panel[1] + 18
        status = tx["thinking"] if self.renderer.thinking else tx["idle"]
        draw.text((x, y), tx["force"], font=self.font_subtitle, fill=(222, 255, 247, 245))
        draw.text((panel[2] - 90, y), status, font=self.font_small, fill=(255, 226, 136, 235) if self.renderer.thinking else (153, 221, 211, 230))
        y += 30

        if runtime_decision:
            decision_title = tx["decision"]
            label = runtime_decision.get("label", tx["unknown"])
            conf = pct(runtime_decision.get("confidence", 0))
            draw.text((x, y), f"{decision_title}: {label}", font=self.font_body, fill=(255, 238, 184, 242))
            draw.text((panel[2] - 78, y), conf, font=self.font_small, fill=(255, 225, 132, 226))
            y += 23

        headline = f"{tx['dominant']}: {dominant.get('label', tx['unknown'])}"
        draw.text((x, y), headline, font=self.font_body, fill=(235, 255, 247, 240))
        y += 23
        subline = f"{tx['action']}: {dominant.get('action_label', tx['unknown'])}"
        draw.text((x, y), subline, font=self.font_small, fill=(168, 206, 199, 225))
        y += 28
        confline = f"{tx['confidence']}: {confidence.get('label', tx['unknown'])}"
        draw.text((x, y), confline, font=self.font_small, fill=(202, 228, 222, 230))
        y += 26

        y = self.draw_progress(draw, x, y, 158, tx["strength"], dynamics.get("resultant_strength", 0), (98, 232, 215))
        y = self.draw_progress(draw, x + 188, y - 38, 158, tx["maturity"], dynamics.get("maturity", 0), (245, 176, 74))
        y = self.draw_progress(draw, x, y + 2, 158, tx["differentiation"], dynamics.get("differentiation", 0), (226, 82, 160))
        y = self.draw_progress(draw, x + 188, y - 38, 158, tx["entropy"], dynamics.get("entropy", 0), (126, 104, 244))
        y += 12

        draw.line((x, y, panel[2] - 22, y), fill=(135, 215, 204, 46), width=1)
        y += 16
        draw.text((x, y), tx["growth"], font=self.font_subtitle, fill=(224, 255, 247, 240))
        y += 25
        deltas = latest.get("visible_delta") or []
        if deltas:
            for item in deltas[:4]:
                label = str(item.get("label", item.get("anchor", tx["changed"])))
                delta = float(item.get("delta", 0.0))
                sign = "+" if delta >= 0 else ""
                color = (117, 236, 213, 230) if delta >= 0 else (255, 129, 129, 230)
                draw.text((x, y), label, font=self.font_small, fill=(193, 223, 217, 228))
                draw.text((panel[2] - 92, y), f"{sign}{delta:.3f}", font=self.font_small, fill=color)
                y += 21
        else:
            for line in wrap_text(draw, tx["no_growth"], self.font_small, panel[2] - panel[0] - 44)[:3]:
                draw.text((x, y), line, font=self.font_small, fill=(178, 211, 204, 224))
                y += 20

    def draw_console(self, phase: float) -> Image.Image:
        self.button_zones = []
        image = Image.new("RGBA", (self.console_w, self.console_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image, "RGBA")
        pulse = (math.sin(phase * 1.1) + 1) * 0.5
        self.add_soft_glow(image, (116, 108), 160, (30, 226, 205), 44)
        self.add_soft_glow(image, (312, 354), 170, (233, 72, 154), 36)
        self.add_soft_glow(image, (710, 62), 130, (248, 188, 68), 30 + int(pulse * 12))
        draw.rounded_rectangle((8, 8, self.console_w - 8, self.console_h - 8), radius=30, fill=(7, 13, 10, 238), outline=(218, 232, 207, 72), width=1)
        draw.line((36, 66, self.console_w - 36, 66), fill=(132, 218, 206, 48), width=1)
        agent = self.data.get("agent", {})
        agent_name = fit_text(draw, agent.get("name", self.text["title"]), self.font_body, 238)
        draw.text((34, 16), self.text["title"], font=self.font_title, fill=(239, 255, 247, 245))
        draw.text((34, 50), agent_name, font=self.font_body, fill=(229, 255, 247, 242))
        draw.text((34, 69), self.text["subtitle"], font=self.font_micro, fill=(161, 202, 194, 220))
        meta = f"{self.text['stage']}: {agent.get('stage', '')}   {self.text['count']}: {agent.get('interaction_count', 0)}   {self.text['type']}: {agent.get('type_label', '')}"
        draw.text((244, 32), fit_text(draw, meta, self.font_small, 288), font=self.font_small, fill=(178, 214, 205, 225))

        self.draw_button(draw, (548, 22, 614, 46), self.text["labels"], "labels", self.show_labels)
        self.draw_button(draw, (622, 22, 688, 46), self.text["topmost"], "topmost", self.topmost)
        self.draw_button(draw, (696, 22, 762, 46), self.text["collapse"], "collapse")
        self.draw_button(draw, (770, 22, 800, 46), "×", "quit")

        orb_size = self.console_orb_size
        orb_x = 52
        orb_y = 90 + (292 - orb_size) // 2
        self.orb_rect = (orb_x, orb_y, orb_x + orb_size, orb_y + orb_size)
        if self.renderer.formation >= 0.18:
            grid_alpha = int(3 + self.renderer.formation * 8)
            cx = orb_x + orb_size * 0.50
            cy = orb_y + orb_size * 0.50
            radius = orb_size * 0.48
            top = 76
            bottom = 378
            left = 36
            right = 394
            gap = 8
            for gx in range(64, 396, 48):
                dx = gx - cx
                if abs(dx) < radius:
                    dy = math.sqrt(max(0.0, radius * radius - dx * dx))
                    draw.line((gx, top, gx, cy - dy - gap), fill=(220, 226, 205, grid_alpha), width=1)
                    draw.line((gx, cy + dy + gap, gx, bottom), fill=(220, 226, 205, grid_alpha), width=1)
                else:
                    draw.line((gx, top, gx, bottom), fill=(220, 226, 205, grid_alpha), width=1)
            for gy in range(92, 372, 48):
                dy = gy - cy
                if abs(dy) < radius:
                    dx = math.sqrt(max(0.0, radius * radius - dy * dy))
                    draw.line((left, gy, cx - dx - gap, gy), fill=(220, 226, 205, max(2, grid_alpha - 1)), width=1)
                    draw.line((cx + dx + gap, gy, right, gy), fill=(220, 226, 205, max(2, grid_alpha - 1)), width=1)
                else:
                    draw.line((left, gy, right, gy), fill=(220, 226, 205, max(2, grid_alpha - 1)), width=1)
            draw.rectangle((68, 82, 370, 374), outline=(222, 226, 205, max(4, grid_alpha)), width=1)
        self.add_soft_glow(image, (orb_x + orb_size * 0.50, orb_y + orb_size * 0.52), orb_size * 0.62, (62, 239, 220), 46)
        self.add_soft_glow(image, (orb_x + orb_size * 0.67, orb_y + orb_size * 0.28), orb_size * 0.36, (255, 176, 66), 30)

        dragging = self.drag_mode in {"rotate", "window"}
        highlight = None if dragging else (self.hovered_region.get("id") if self.hovered_region else None)
        fast = False
        orb = self.renderer.render(phase, auto_spin=self.drag_mode != "rotate", highlight_id=highlight, fast=fast)
        image.alpha_composite(orb, (orb_x, orb_y))
        draw.ellipse(
            (orb_x + 18, orb_y + orb_size - 24, orb_x + orb_size - 18, orb_y + orb_size + 10),
            fill=(19, 218, 205, 22),
        )
        hint_box = (58, 404, 334, 430)
        draw.rounded_rectangle(hint_box, radius=13, fill=(4, 12, 13, 172), outline=(112, 230, 216, 54))
        draw.text((72, 410), self.text["hint"], font=self.font_small, fill=(185, 225, 216, 224))

        if self.show_labels and not dragging:
            for region in sorted(self.renderer.regions, key=lambda item: float(item.get("area", 0)), reverse=True)[:10]:
                self.draw_domain_label(draw, region, (orb_x, orb_y))
        if self.hovered_region and self.mode == "console" and not dragging:
            self.draw_domain_label(draw, self.hovered_region, (orb_x, orb_y))
            self.draw_hover_card(draw, self.hovered_region, (self.pointer_x, self.pointer_y))

        self.draw_analysis_panel(image, draw, phase)
        return image

    def draw_compact(self, phase: float) -> Image.Image:
        highlight = self.hovered_region.get("id") if self.hovered_region else None
        image = self.renderer.render(phase, highlight_id=highlight, fast=False)
        self.orb_rect = (0, 0, self.compact_size, self.compact_size)
        return image

    def tick(self) -> None:
        tick_started = time.perf_counter()
        phase = time.perf_counter() - self.phase_start
        self.read_signal(phase)
        self.reload_visible_if_changed(phase)
        if self.drag_mode:
            self.hovered_region = None
            self.hide_tooltip()
        else:
            self.update_hover()
        if self.drag_mode == "window" and self.tk_image is not None:
            self.root.after(16, self.tick)
            return
        image = self.draw_console(phase) if self.mode == "console" else self.draw_compact(phase)
        self.present_image(image)
        elapsed_ms = (time.perf_counter() - tick_started) * 1000
        self.root.after(max(1, int(33 - elapsed_ms)), self.tick)

    def run(self) -> None:
        self.tick()
        self.root.mainloop()


def load_data(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_signal(thinking: bool, path: Path = SIGNAL_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"thinking": thinking, "updated_at": time.time()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_ready(agent_id: str, visible: Path, signal: Path, path: Path = READY_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": "pdk.desktop_orb_ready.v1",
                "agent_id": agent_id,
                "visible": str(visible.resolve()),
                "signal": str(signal.resolve()),
                "pid": os.getpid(),
                "ready_at": time.time(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    lang = detect_ui_language()
    cli_text = {
        "zh": {
            "description": "透明桌面 PKM 人格球宠物",
            "console": "以桌面观察台模式启动",
            "x": "初始窗口 x 坐标",
            "y": "初始窗口 y 坐标",
            "preview": "渲染一张透明预览 PNG 后退出",
            "preview_console": "渲染一张桌面观察台预览 PNG 后退出",
            "set_thinking": "设置桌面人格球思考信号后退出",
        },
        "en": {
            "description": "Transparent desktop PKM orb pet",
            "console": "start in desktop observatory mode",
            "x": "initial window x position",
            "y": "initial window y position",
            "preview": "render one transparent preview PNG and exit",
            "preview_console": "render one desktop observatory preview PNG and exit",
            "set_thinking": "set desktop orb thinking signal and exit",
        },
    }[lang]
    parser = argparse.ArgumentParser(description=cli_text["description"])
    parser.add_argument("--agent-id", default="default", help=argparse.SUPPRESS)
    parser.add_argument("--visible", type=Path, default=DEFAULT_VISIBLE)
    parser.add_argument("--signal", type=Path, default=SIGNAL_FILE)
    parser.add_argument("--ready", type=Path, default=READY_FILE)
    parser.add_argument("--size", type=int, default=112)
    parser.add_argument("--opacity", type=float, default=0.88)
    parser.add_argument("--console", action="store_true", help=cli_text["console"])
    parser.add_argument("--x", type=int, help=cli_text["x"])
    parser.add_argument("--y", type=int, help=cli_text["y"])
    parser.add_argument("--preview", type=Path, help=cli_text["preview"])
    parser.add_argument("--preview-console", type=Path, help=cli_text["preview_console"])
    parser.add_argument("--preview-thinking", action="store_true")
    parser.add_argument("--set-thinking", choices=["on", "off"], help=cli_text["set_thinking"])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.set_thinking:
        write_signal(args.set_thinking == "on", args.signal)
        print(f"thinking={args.set_thinking}")
        return 0
    data = load_data(args.visible)
    if args.preview:
        renderer = OrbRenderer(data, size=args.size)
        renderer.set_thinking(bool(args.preview_thinking))
        image = renderer.render(0.1)
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        image.save(args.preview)
        print(f"wrote {args.preview}")
        return 0
    if args.preview_console:
        app = DesktopOrb(
            data,
            size=args.size,
            opacity=clamp(float(args.opacity), 0.25, 1.0),
            visible_path=args.visible,
            signal_path=args.signal,
            initial_x=args.x,
            initial_y=args.y,
        )
        app.root.withdraw()
        app.set_mode("console")
        app.renderer.set_thinking(bool(args.preview_thinking))
        image = app.draw_console(0.1)
        args.preview_console.parent.mkdir(parents=True, exist_ok=True)
        image.save(args.preview_console)
        app.root.destroy()
        print(f"wrote {args.preview_console}")
        return 0
    app = DesktopOrb(
        data,
        size=args.size,
        opacity=clamp(float(args.opacity), 0.25, 1.0),
        visible_path=args.visible,
        signal_path=args.signal,
        initial_x=args.x,
        initial_y=args.y,
    )
    if args.console:
        app.set_mode("console")
    app.root.update_idletasks()
    write_ready(args.agent_id, args.visible, args.signal, args.ready)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
