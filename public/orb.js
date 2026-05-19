const dock = document.getElementById("orbDock");
const canvas = document.getElementById("orbCanvas");
const ctx = canvas.getContext("2d", { alpha: true });

let width = 1;
let height = 1;
let dpr = 1;
let data = null;
let regions = [];
let confidence = [];
let cells = [];
let ripples = [];
let yaw = -0.55;
let pitch = 0.12;
let roll = 0;
let dockLeft = 0;
let dockTop = 0;
let dockReady = false;
let pointerDown = false;
let draggingDock = false;
let dragOffsetX = 0;
let dragOffsetY = 0;
let downX = 0;
let downY = 0;

function v(x, y, z) {
  return { x, y, z };
}

function add(a, b) {
  return v(a.x + b.x, a.y + b.y, a.z + b.z);
}

function mul(a, s) {
  return v(a.x * s, a.y * s, a.z * s);
}

function dot(a, b) {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

function cross(a, b) {
  return v(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x);
}

function normalize(point) {
  const len = Math.hypot(point.x, point.y, point.z) || 1;
  return v(point.x / len, point.y / len, point.z / len);
}

function directionFromAngles(theta, phi) {
  return normalize(v(
    Math.sin(phi) * Math.cos(theta),
    Math.cos(phi),
    Math.sin(phi) * Math.sin(theta),
  ));
}

function direction(item) {
  if (item._dir) return item._dir;
  if (item.direction) return normalize(v(item.direction[0], item.direction[1], item.direction[2]));
  return directionFromAngles(item.theta, item.phi);
}

function tangentBasis(dir) {
  const up = Math.abs(dir.y) > 0.86 ? v(1, 0, 0) : v(0, 1, 0);
  const t1 = normalize(cross(up, dir));
  const t2 = normalize(cross(dir, t1));
  return [t1, t2];
}

function rotate(point) {
  const cy = Math.cos(yaw);
  const sy = Math.sin(yaw);
  const cp = Math.cos(pitch);
  const sp = Math.sin(pitch);
  const cr = Math.cos(roll);
  const sr = Math.sin(roll);

  const x1 = point.x * cy - point.z * sy;
  const z1 = point.x * sy + point.z * cy;
  const y1 = point.y * cp - z1 * sp;
  const z2 = point.y * sp + z1 * cp;
  const x2 = x1 * cr - y1 * sr;
  const y2 = x1 * sr + y1 * cr;
  return v(x2, y2, z2);
}

function inverseRotate(point) {
  const cr = Math.cos(-roll);
  const sr = Math.sin(-roll);
  const cp = Math.cos(-pitch);
  const sp = Math.sin(-pitch);
  const cy = Math.cos(-yaw);
  const sy = Math.sin(-yaw);

  const x1 = point.x * cr - point.y * sr;
  const y1 = point.x * sr + point.y * cr;
  const y2 = y1 * cp - point.z * sp;
  const z1 = y1 * sp + point.z * cp;
  const x2 = x1 * cy - z1 * sy;
  const z2 = x1 * sy + z1 * cy;
  return normalize(v(x2, y2, z2));
}

function project(point) {
  const r = rotate(point);
  const distance = 4.1;
  const scale = Math.min(width, height) * 1.43 / (distance - r.z);
  return {
    x: width * 0.5 + r.x * scale,
    y: height * 0.5 - r.y * scale,
    z: r.z,
    scale,
  };
}

function hexToRgb(hex) {
  const raw = hex.replace("#", "");
  return {
    r: parseInt(raw.slice(0, 2), 16),
    g: parseInt(raw.slice(2, 4), 16),
    b: parseInt(raw.slice(4, 6), 16),
  };
}

function rgbString(rgb, alpha) {
  return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`;
}

function withAlpha(hex, alpha) {
  return rgbString(hexToRgb(hex), alpha);
}

function mixRgb(a, b, t) {
  return {
    r: Math.round(a.r * (1 - t) + b.r * t),
    g: Math.round(a.g * (1 - t) + b.g * t),
    b: Math.round(a.b * (1 - t) + b.b * t),
  };
}

function dynamicColor(baseHex, phase, bias = 0) {
  const base = hexToRgb(baseHex);
  const teal = { r: 72, g: 156, b: 148 };
  const amber = { r: 207, g: 151, b: 72 };
  const rose = { r: 164, g: 86, b: 105 };
  const t1 = (Math.sin(phase * 0.42 + bias) + 1) * 0.5;
  const t2 = (Math.sin(phase * 0.31 + bias * 1.7) + 1) * 0.5;
  return mixRgb(mixRgb(base, teal, 0.22 * t1), mixRgb(amber, rose, t2), 0.16);
}

function nearestRegion(dir) {
  let best = regions[0] || null;
  let bestScore = -Infinity;
  for (const region of regions) {
    const score = dot(dir, region._dir);
    if (score > bestScore) {
      best = region;
      bestScore = score;
    }
  }
  return best;
}

function buildCells() {
  const density = data?.model?.substrate?.density || 0.68;
  const count = data?.model?.substrate?.seed_count || 116;
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  cells = [];
  for (let i = 0; i < count; i += 1) {
    const y = 1 - ((i + 0.5) / count) * 2;
    const ring = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = i * goldenAngle;
    const dir = normalize(v(Math.cos(theta) * ring, y, Math.sin(theta) * ring));
    const owner = nearestRegion(dir);
    const [t1, t2] = tangentBasis(dir);
    const ownerStrength = owner ? owner.value * 0.14 + owner.area * 2.2 : 0.18;
    cells.push({
      _dir: dir,
      _basis: [t1, t2],
      color: owner ? owner.color : "#6d877f",
      phase: theta + i * 0.17,
      size: 0.075 + density * 0.048 + ownerStrength * 0.020,
      alpha: 0.020 + density * 0.026 + ownerStrength * 0.010,
    });
  }
}

function hydrate(nextData) {
  data = nextData;
  regions = (nextData.model.regions || []).map((region) => {
    region._dir = direction(region);
    region._basis = tangentBasis(region._dir);
    region._fieldStrength = region.height * (0.62 + region.area * 4.1);
    region._phase = region.theta * 1.93;
    return region;
  });
  confidence = (nextData.model.confidence_modes || []).map((mode) => {
    mode._dir = direction(mode);
    mode._basis = tangentBasis(mode._dir);
    mode._fieldStrength = mode.height * 0.24;
    mode._phase = mode.theta;
    return mode;
  });
  buildCells();
}

function rippleField(dir, phase) {
  let amount = 0;
  const next = [];
  for (const ripple of ripples) {
    const age = phase - ripple.started;
    if (age > 2.8) continue;
    next.push(ripple);
    const angle = Math.acos(Math.max(-1, Math.min(1, dot(dir, ripple.dir))));
    const front = age * 0.58;
    const band = Math.exp(-((angle - front) ** 2) / 0.0065);
    const centerPull = Math.exp(-(angle ** 2) / 0.020) * Math.exp(-age * 2.2);
    const wave = Math.sin((angle - age * 0.54) * 36) * band;
    amount += ripple.strength * (wave * Math.exp(-age * 0.82) - centerPull * 0.20);
  }
  ripples = next;
  return amount;
}

function personalityField(dir, phase) {
  let amount = 0;
  for (const region of regions) {
    const influence = Math.pow(Math.max(0, dot(dir, region._dir)), 8.1);
    const breathing = 1 + Math.sin(phase * 0.62 + region._phase) * 0.035;
    amount += influence * region._fieldStrength * breathing;
  }
  for (const mode of confidence) {
    const influence = Math.pow(Math.max(0, dot(dir, mode._dir)), 12);
    amount += influence * mode._fieldStrength * (1 + Math.sin(phase * 0.84 + mode._phase) * 0.025);
  }
  amount += rippleField(dir, phase);
  return amount;
}

function surfacePoint(dir, radius, phase) {
  const subtle =
    Math.sin(dir.x * 5.2 + phase * 0.50) * 0.007 +
    Math.sin(dir.z * 6.4 - phase * 0.38) * 0.006 +
    Math.sin((dir.x + dir.y) * 7.3 + phase * 0.27) * 0.005;
  return mul(dir, radius + personalityField(dir, phase) * 0.24 + subtle);
}

function resize() {
  dpr = Math.min(window.devicePixelRatio || 1, 2);
  width = dock.clientWidth;
  height = dock.clientHeight;
  canvas.width = Math.floor(width * dpr);
  canvas.height = Math.floor(height * dpr);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  if (!dockReady) {
    const rect = dock.getBoundingClientRect();
    dockLeft = rect.left;
    dockTop = rect.top;
    dock.style.left = `${dockLeft}px`;
    dock.style.top = `${dockTop}px`;
    dock.style.transform = "none";
    dockReady = true;
  }
}

function clampDockPosition() {
  const margin = Math.max(24, Math.min(width, height) * 0.08);
  const maxLeft = window.innerWidth - margin;
  const maxTop = window.innerHeight - margin;
  dockLeft = Math.min(maxLeft, Math.max(margin - width, dockLeft));
  dockTop = Math.min(maxTop, Math.max(margin - height, dockTop));
  dock.style.left = `${dockLeft}px`;
  dock.style.top = `${dockTop}px`;
}

function beginPath(points) {
  ctx.beginPath();
  points.forEach((point, index) => {
    const p = project(point);
    if (index === 0) ctx.moveTo(p.x, p.y);
    else ctx.lineTo(p.x, p.y);
  });
}

function drawPath(points, color, alpha, lineWidth) {
  if (points.length < 2) return;
  beginPath(points);
  ctx.strokeStyle = color.startsWith("#") ? withAlpha(color, alpha) : color;
  ctx.lineWidth = lineWidth;
  ctx.stroke();
}

function drawAura(phase) {
  const center = project(v(0, 0, 0));
  const radius = Math.abs(project(v(1.42, 0, 0)).x - center.x);
  const aura = ctx.createRadialGradient(center.x, center.y, radius * 0.05, center.x, center.y, radius * 1.22);
  aura.addColorStop(0, "rgba(244, 239, 214, 0.12)");
  aura.addColorStop(0.38, "rgba(92, 153, 145, 0.11)");
  aura.addColorStop(0.65, "rgba(154, 98, 91, 0.08)");
  aura.addColorStop(1, "rgba(6, 10, 8, 0)");
  ctx.fillStyle = aura;
  ctx.beginPath();
  ctx.arc(center.x, center.y, radius * (1.01 + Math.sin(phase * 0.36) * 0.018), 0, Math.PI * 2);
  ctx.fill();
}

function drawCore(phase) {
  const center = project(v(0, 0, 0));
  const radius = Math.abs(project(v(1.02, 0, 0)).x - center.x);
  const core = ctx.createRadialGradient(
    center.x - radius * 0.26,
    center.y - radius * 0.34,
    radius * 0.03,
    center.x,
    center.y,
    radius * 1.04,
  );
  core.addColorStop(0, "rgba(248, 239, 205, 0.42)");
  core.addColorStop(0.22, "rgba(196, 216, 204, 0.23)");
  core.addColorStop(0.48, "rgba(101, 139, 135, 0.17)");
  core.addColorStop(0.76, "rgba(109, 73, 82, 0.12)");
  core.addColorStop(1, "rgba(6, 10, 8, 0)");
  ctx.fillStyle = core;
  ctx.beginPath();
  ctx.ellipse(center.x, center.y, radius * 1.02, radius * 0.99, Math.sin(phase * 0.18) * 0.04, 0, Math.PI * 2);
  ctx.fill();
}

function cellPolygon(cell, phase) {
  const [t1, t2] = cell._basis;
  const points = [];
  const size = cell.size * (1 + Math.sin(phase * 0.36 + cell.phase) * 0.09);
  for (let i = 0; i < 12; i += 1) {
    const a = (Math.PI * 2 * i) / 12;
    const wobble = 1 + Math.sin(a * 3 + cell.phase + phase * 0.13) * 0.14;
    const angular = size * wobble;
    const dir = normalize(add(
      mul(cell._dir, Math.cos(angular)),
      add(mul(t1, Math.cos(a) * Math.sin(angular)), mul(t2, Math.sin(a) * Math.sin(angular))),
    ));
    points.push(surfacePoint(dir, 1.04, phase));
  }
  return points;
}

function drawCells(phase) {
  const sorted = [...cells].sort((a, b) => project(a._dir).z - project(b._dir).z);
  for (const cell of sorted) {
    const depth = project(cell._dir).z;
    if (depth < -1.04) continue;
    const rgb = dynamicColor(cell.color, phase, cell.phase);
    const alpha = cell.alpha * (depth > -0.55 ? 1 : 0.38);
    beginPath(cellPolygon(cell, phase));
    ctx.closePath();
    ctx.fillStyle = rgbString(rgb, alpha);
    ctx.fill();
    ctx.strokeStyle = rgbString(rgb, alpha * 0.96);
    ctx.lineWidth = 0.55;
    ctx.stroke();
  }
}

function patchPolygon(item, phase, scale = 1) {
  const dir = item._dir;
  const [t1, t2] = item._basis;
  const areaRadius = (0.13 + Math.sqrt(item.area || 0.05) * 0.70) * scale;
  const roughness = item.roughness || 0.2;
  const points = [];
  for (let i = 0; i < 42; i += 1) {
    const a = (Math.PI * 2 * i) / 42;
    const wobble =
      1
      + Math.sin(a * 3 + item.theta * 1.5 + phase * 0.21) * roughness * 0.12
      + Math.sin(a * 7 + item.phi * 2.4 - phase * 0.17) * roughness * 0.07;
    const angular = areaRadius * wobble;
    const rim = normalize(add(
      mul(dir, Math.cos(angular)),
      add(mul(t1, Math.cos(a) * Math.sin(angular)), mul(t2, Math.sin(a) * Math.sin(angular))),
    ));
    points.push(surfacePoint(rim, 1.14 + Math.max(item.height || 0, -0.10) * 0.20, phase));
  }
  return points;
}

function drawRegions(phase) {
  const sorted = [...regions].sort((a, b) => project(a._dir).z - project(b._dir).z);
  for (const region of sorted) {
    const depth = project(region._dir).z;
    if (depth < -0.98) continue;
    const rgb = dynamicColor(region.color, phase, region.theta);
    const alpha = 0.12 + region.area * 0.92 + Math.max(depth, 0) * 0.03;
    beginPath(patchPolygon(region, phase, 0.92));
    ctx.closePath();
    ctx.save();
    ctx.shadowColor = rgbString(rgb, 0.18);
    ctx.shadowBlur = 16;
    ctx.fillStyle = rgbString(rgb, alpha);
    ctx.fill();
    ctx.restore();
    ctx.strokeStyle = rgbString(rgb, 0.18 + region.stability * 0.20);
    ctx.lineWidth = 0.9 + region.boundary_width * 1.1;
    ctx.stroke();
  }
}

function drawFlowLines(phase) {
  for (let p = 0.30; p < Math.PI - 0.24; p += Math.PI / 9) {
    const points = [];
    for (let t = 0; t <= Math.PI * 2 + 0.02; t += Math.PI / 72) {
      const drift = Math.sin(phase * 0.32 + p * 2.1) * 0.035;
      const dir = directionFromAngles(t + drift, p + Math.sin(t * 2 + phase * 0.20) * 0.018);
      points.push(surfacePoint(dir, 1.17, phase));
    }
    drawPath(points, "#d9e3d2", 0.035, 0.65);
  }
  for (let t = 0; t < Math.PI * 2; t += Math.PI / 11) {
    const points = [];
    for (let p = 0.18; p <= Math.PI - 0.18; p += Math.PI / 74) {
      const dir = directionFromAngles(t + Math.sin(phase * 0.18 + p * 3.3) * 0.020, p);
      points.push(surfacePoint(dir, 1.18, phase));
    }
    drawPath(points, "#9eb5ad", 0.026, 0.55);
  }
}

function drawRippleRings(phase) {
  for (const ripple of ripples) {
    const age = phase - ripple.started;
    if (age <= 0 || age > 2.8) continue;
    const [t1, t2] = tangentBasis(ripple.dir);
    for (let ring = 0; ring < 2; ring += 1) {
      const angle = age * (0.56 + ring * 0.16);
      if (angle <= 0 || angle >= Math.PI * 0.94) continue;
      const points = [];
      for (let i = 0; i <= 96; i += 1) {
        const a = (Math.PI * 2 * i) / 96;
        const dir = normalize(add(
          mul(ripple.dir, Math.cos(angle)),
          add(mul(t1, Math.cos(a) * Math.sin(angle)), mul(t2, Math.sin(a) * Math.sin(angle))),
        ));
        points.push(surfacePoint(dir, 1.205, phase));
      }
      const alpha = Math.max(0, 0.34 * Math.exp(-age * 0.92) * (ring ? 0.56 : 1));
      drawPath(points, `rgba(235, 246, 228, ${alpha})`, 1, 1.2 - ring * 0.25);
    }
  }
}

function drawSpecular(phase) {
  const center = project(v(0, 0, 0));
  const radius = Math.abs(project(v(0.82, 0, 0)).x - center.x);
  const glint = ctx.createRadialGradient(
    center.x - radius * 0.36 + Math.sin(phase * 0.25) * radius * 0.10,
    center.y - radius * 0.42,
    0,
    center.x - radius * 0.22,
    center.y - radius * 0.28,
    radius * 0.50,
  );
  glint.addColorStop(0, "rgba(255, 251, 224, 0.22)");
  glint.addColorStop(0.34, "rgba(221, 241, 226, 0.080)");
  glint.addColorStop(1, "rgba(255, 255, 255, 0)");
  ctx.fillStyle = glint;
  ctx.beginPath();
  ctx.ellipse(center.x - radius * 0.20, center.y - radius * 0.26, radius * 0.45, radius * 0.26, -0.44, 0, Math.PI * 2);
  ctx.fill();
}

function drawOrb(time) {
  const phase = time * 0.001;
  yaw += 0.0021;
  pitch = 0.12 + Math.sin(phase * 0.24) * 0.07;
  roll = Math.sin(phase * 0.18) * 0.035;

  ctx.clearRect(0, 0, width, height);
  if (!data) return;
  drawAura(phase);
  drawCore(phase);
  drawCells(phase);
  drawRegions(phase);
  drawFlowLines(phase);
  drawRippleRings(phase);
  drawSpecular(phase);
}

function eventToLocal(event) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  };
}

function clickDirection(local) {
  const radius = Math.min(width, height) * 0.36;
  const nx = (local.x - width * 0.5) / radius;
  const ny = (height * 0.5 - local.y) / radius;
  const d2 = nx * nx + ny * ny;
  if (d2 > 1.15) return null;
  const z = Math.sqrt(Math.max(0.02, 1 - Math.min(d2, 1)));
  return inverseRotate(v(nx, ny, z));
}

function addRipple(local, phase) {
  const dir = clickDirection(local);
  if (!dir) return;
  ripples.push({
    dir,
    started: phase,
    strength: 0.135,
  });
  if (ripples.length > 6) ripples.shift();
}

dock.addEventListener("pointerdown", (event) => {
  pointerDown = true;
  draggingDock = false;
  downX = event.clientX;
  downY = event.clientY;
  const rect = dock.getBoundingClientRect();
  dragOffsetX = event.clientX - rect.left;
  dragOffsetY = event.clientY - rect.top;
  dock.setPointerCapture(event.pointerId);
});

dock.addEventListener("pointermove", (event) => {
  if (!pointerDown) return;
  const moved = Math.hypot(event.clientX - downX, event.clientY - downY);
  if (moved > 5) draggingDock = true;
  if (!draggingDock) return;
  dockLeft = event.clientX - dragOffsetX;
  dockTop = event.clientY - dragOffsetY;
  clampDockPosition();
});

dock.addEventListener("pointerup", (event) => {
  const moved = Math.hypot(event.clientX - downX, event.clientY - downY);
  pointerDown = false;
  dock.releasePointerCapture(event.pointerId);
  if (moved <= 5) addRipple(eventToLocal(event), performance.now() * 0.001);
});

dock.addEventListener("pointercancel", () => {
  pointerDown = false;
  draggingDock = false;
});

window.addEventListener("resize", () => {
  resize();
  clampDockPosition();
});

async function loadData() {
  const response = await fetch("./pkm_visible.json", { cache: "no-store" });
  hydrate(await response.json());
}

function animate(time) {
  requestAnimationFrame(animate);
  drawOrb(time);
}

resize();
loadData();
requestAnimationFrame(animate);
