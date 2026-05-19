const mount = document.getElementById("canvasMount");
const labelLayer = document.getElementById("labelLayer");
const canvas = document.createElement("canvas");
const ctx = canvas.getContext("2d");
mount.appendChild(canvas);

let data = null;
let width = 1;
let height = 1;
let yaw = -0.62;
let pitch = 0.12;
let zoom = 0.96;
let dragging = false;
let lastX = 0;
let lastY = 0;
let downX = 0;
let downY = 0;
let labelMode = "hover";
let showGrowthPath = false;
let pointer = { x: -9999, y: -9999 };
let hovered = null;
let selected = null;
let interactivePoints = [];
let fieldRegions = [];
let fieldModes = [];
let potentialCells = [];
let lastInteractionAt = 0;
let lastFrameAt = 0;

function resize() {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  width = mount.clientWidth;
  height = mount.clientHeight;
  canvas.width = Math.floor(width * dpr);
  canvas.height = Math.floor(height * dpr);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function v(x, y, z) {
  return { x, y, z };
}

function add(a, b) {
  return v(a.x + b.x, a.y + b.y, a.z + b.z);
}

function mul(a, s) {
  return v(a.x * s, a.y * s, a.z * s);
}

function normalize(point) {
  const len = Math.hypot(point.x, point.y, point.z) || 1;
  return v(point.x / len, point.y / len, point.z / len);
}

function cross(a, b) {
  return v(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x);
}

function dot(a, b) {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

function rotate(point) {
  const cy = Math.cos(yaw);
  const sy = Math.sin(yaw);
  const cp = Math.cos(pitch);
  const sp = Math.sin(pitch);
  const x1 = point.x * cy - point.z * sy;
  const z1 = point.x * sy + point.z * cy;
  const y1 = point.y * cp - z1 * sp;
  const z2 = point.y * sp + z1 * cp;
  return { x: x1, y: y1, z: z2 };
}

function project(point) {
  const r = rotate(point);
  const distance = 4.15;
  const scale = (Math.min(width, height) * 1.28 * zoom) / (distance - r.z);
  return {
    x: width * 0.50 + r.x * scale,
    y: height * 0.53 - r.y * scale,
    z: r.z,
    scale,
  };
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

function withAlpha(hex, alpha) {
  const raw = hex.replace("#", "");
  const r = parseInt(raw.slice(0, 2), 16);
  const g = parseInt(raw.slice(2, 4), 16);
  const b = parseInt(raw.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function tangentBasis(dir) {
  const up = Math.abs(dir.y) > 0.88 ? v(1, 0, 0) : v(0, 1, 0);
  const t1 = normalize(cross(up, dir));
  const t2 = normalize(cross(dir, t1));
  return [t1, t2];
}

function nearestRegionForDir(dir) {
  let best = fieldRegions[0] || null;
  let bestScore = -Infinity;
  for (const region of fieldRegions) {
    const score = dot(dir, region._dir);
    if (score > bestScore) {
      best = region;
      bestScore = score;
    }
  }
  return best;
}

function buildPotentialCells(nextData) {
  const seedCount = nextData.model.substrate?.seed_count || 88;
  const density = nextData.model.substrate?.density || 0.56;
  const cells = [];
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < seedCount; i += 1) {
    const y = 1 - ((i + 0.5) / seedCount) * 2;
    const radius = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = i * goldenAngle;
    const dir = normalize(v(Math.cos(theta) * radius, y, Math.sin(theta) * radius));
    const owner = nearestRegionForDir(dir);
    const [t1, t2] = tangentBasis(dir);
    const activation = owner ? Math.max(0.18, owner.area * 3.6 + owner.value * 0.16) : 0.22;
    cells.push({
      _dir: dir,
      _basis: [t1, t2],
      color: owner ? owner.color : "#6d877f",
      phase: theta + i * 0.17,
      size: 0.070 + density * 0.045 + activation * 0.030,
      alpha: 0.018 + density * 0.030 + activation * 0.014,
    });
  }
  potentialCells = cells;
}

function hydrateModel(nextData) {
  fieldRegions = (nextData.model.regions || []).map((region) => {
    region._dir = direction(region);
    region._basis = tangentBasis(region._dir);
    region._fieldStrength = region.height * (0.62 + region.area * 4.6);
    region._phase = region.theta * 2.1;
    region._facets = (region.facets || []).map((facet) => {
      facet._dir = directionFromAngles(facet.theta, facet.phi);
      facet._fieldStrength = (facet.height * 0.22) * (0.7 + facet.weight * 0.8);
      facet._curveStrength = facet.curvature * 0.025 * (0.7 + facet.weight * 0.8);
      return facet;
    });
    return region;
  });
  fieldModes = (nextData.model.confidence_modes || []).map((mode) => {
    mode._dir = direction(mode);
    mode._fieldStrength = mode.height * 0.36;
    mode._phase = mode.theta;
    return mode;
  });
  buildPotentialCells(nextData);
}

function personalityField(dir, phase, quality) {
  if (!data) return 0;
  let amount = 0;
  const includeFineDetail = quality !== "fast";
  for (const region of fieldRegions) {
    const influence = Math.pow(Math.max(0, dot(dir, region._dir)), includeFineDetail ? 8.4 : 7.2);
    const breathing = 1 + Math.sin(phase * 0.9 + region._phase) * (includeFineDetail ? 0.045 : 0.018);
    amount += influence * region._fieldStrength * breathing;
    if (includeFineDetail) {
      for (const facet of region._facets || []) {
        const facetInfluence = Math.pow(Math.max(0, dot(dir, facet._dir)), 18);
        const curve = Math.sin(phase * 1.25 + facet.theta * 4.7) * facet._curveStrength;
        amount += facetInfluence * (facet._fieldStrength + curve);
      }
    }
  }
  if (includeFineDetail) {
    for (const mode of fieldModes) {
      const influence = Math.pow(Math.max(0, dot(dir, mode._dir)), 12.5);
      const confidencePulse = 1 + Math.sin(phase * 1.4 + mode._phase) * 0.035;
      amount += influence * mode._fieldStrength * confidencePulse;
    }
  }
  return amount;
}

function pointOnBody(theta, phi, baseRadius, influence, phase, quality) {
  const dir = directionFromAngles(theta, phi);
  const waveScale = quality === "fast" ? 0.45 : 1;
  const slowWave =
    (Math.sin(dir.x * 4.2 + phase * 0.62) * 0.010 +
    Math.sin(dir.z * 5.9 - phase * 0.43) * 0.008 +
    Math.sin((dir.x + dir.y + dir.z) * 7.4 + phase * 0.34) * 0.006) * waveScale;
  const radius = baseRadius + personalityField(dir, phase, quality) * influence + slowWave;
  return mul(dir, radius);
}

function drawPath(points, color, alpha, lineWidth = 1) {
  if (points.length < 2) return;
  ctx.beginPath();
  points.forEach((point, index) => {
    const p = project(point);
    if (index === 0) ctx.moveTo(p.x, p.y);
    else ctx.lineTo(p.x, p.y);
  });
  ctx.strokeStyle = withAlpha(color, alpha);
  ctx.lineWidth = lineWidth;
  ctx.stroke();
}

function drawAtmosphere(phase) {
  const center = project(v(0, 0, 0));
  const radius = Math.abs(project(v(1.44, 0, 0)).x - center.x);
  const aura = ctx.createRadialGradient(center.x, center.y, radius * 0.20, center.x, center.y, radius * 1.18);
  aura.addColorStop(0, "rgba(235, 230, 205, 0.11)");
  aura.addColorStop(0.42, "rgba(87, 124, 135, 0.10)");
  aura.addColorStop(0.72, "rgba(151, 102, 96, 0.07)");
  aura.addColorStop(1, "rgba(10, 14, 12, 0)");
  ctx.fillStyle = aura;
  ctx.beginPath();
  ctx.arc(center.x, center.y, radius * (1.02 + Math.sin(phase * 0.55) * 0.015), 0, Math.PI * 2);
  ctx.fill();
}

function drawBaseLayers(phase, quality) {
  drawAtmosphere(phase);
  const center = project(v(0, 0, 0));
  const fast = quality === "fast";
  for (const [index, layer] of data.model.layers.entries()) {
    const screenRadius = Math.abs(project(v(layer.radius, 0, 0)).x - center.x);
    const gradient = ctx.createRadialGradient(
      center.x - screenRadius * 0.30,
      center.y - screenRadius * 0.36,
      screenRadius * 0.04,
      center.x,
      center.y,
      screenRadius * 1.16,
    );
    gradient.addColorStop(0, withAlpha(layer.color, Math.min(0.58, layer.opacity * 2.45)));
    gradient.addColorStop(0.36, withAlpha(layer.color, layer.opacity * 1.04));
    gradient.addColorStop(0.75, withAlpha(layer.color, layer.opacity * 0.40));
    gradient.addColorStop(1, withAlpha(layer.color, 0));
    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.ellipse(center.x, center.y, screenRadius * 1.05, screenRadius * 0.98, -0.02, 0, Math.PI * 2);
    ctx.fill();

    if (fast && index < 2) continue;
    const layerInfluence = layer.id === "core" ? 0.16 : 0.86;
    const latStep = Math.PI / (fast ? 7 : 10);
    const thetaStep = Math.PI / (fast ? 42 : 72);
    const longStep = Math.PI / (fast ? 9 : 14);
    const phiStep = Math.PI / (fast ? 54 : 82);
    for (let p = 0.18; p < Math.PI; p += latStep) {
      const points = [];
      for (let t = 0; t <= Math.PI * 2 + 0.01; t += thetaStep) {
        points.push(pointOnBody(t, p, layer.radius, layerInfluence, phase, quality));
      }
      drawPath(points, layer.color, 0.060 + index * 0.018, 0.72);
    }
    for (let t = 0; t < Math.PI * 2; t += longStep) {
      const points = [];
      for (let p = 0.10; p <= Math.PI - 0.10; p += phiStep) {
        points.push(pointOnBody(t, p, layer.radius, layerInfluence, phase, quality));
      }
      drawPath(points, layer.color, 0.045 + index * 0.014, 0.64);
    }
  }
}

function patchPolygon(item, baseRadius, scale, steps, phase, quality) {
  const dir = direction(item);
  const [t1, t2] = item._basis || tangentBasis(dir);
  const areaRadius = (0.15 + Math.sqrt(item.area || item.weight || 0.05) * 0.82) * scale;
  const roughness = item.roughness || item.curvature || 0.2;
  const heightValue = item.height || 0;
  const points = [];
  for (let i = 0; i < steps; i += 1) {
    const a = (Math.PI * 2 * i) / steps;
    const wobble =
      1
      + Math.sin(a * 3 + item.theta * 1.7 + phase * 0.34) * roughness * 0.18
      + Math.sin(a * 8 + item.phi * 3.1 - phase * 0.22) * roughness * 0.09;
    const angular = areaRadius * wobble;
    const rim = normalize(add(
      mul(dir, Math.cos(angular)),
      add(mul(t1, Math.cos(a) * Math.sin(angular)), mul(t2, Math.sin(a) * Math.sin(angular))),
    ));
    const radius = baseRadius + heightValue * 0.48 + personalityField(rim, phase, quality) * 0.14;
    points.push(mul(rim, radius));
  }
  return points;
}

function fillProjectedPolygon(points, color, alpha, strokeAlpha, lineWidth) {
  if (points.length < 3) return;
  ctx.beginPath();
  points.forEach((point, index) => {
    const p = project(point);
    if (index === 0) ctx.moveTo(p.x, p.y);
    else ctx.lineTo(p.x, p.y);
  });
  ctx.closePath();
  ctx.save();
  ctx.shadowBlur = 18;
  ctx.shadowColor = withAlpha(color, 0.16);
  ctx.fillStyle = withAlpha(color, alpha);
  ctx.fill();
  ctx.restore();
  ctx.strokeStyle = withAlpha(color, strokeAlpha);
  ctx.lineWidth = lineWidth;
  ctx.stroke();
}

function fillPotentialPolygon(points, color, alpha) {
  if (points.length < 3) return;
  ctx.beginPath();
  points.forEach((point, index) => {
    const p = project(point);
    if (index === 0) ctx.moveTo(p.x, p.y);
    else ctx.lineTo(p.x, p.y);
  });
  ctx.closePath();
  ctx.fillStyle = withAlpha(color, alpha);
  ctx.fill();
  ctx.strokeStyle = withAlpha(color, alpha * 1.25);
  ctx.lineWidth = 0.55;
  ctx.stroke();
}

function potentialCellPolygon(cell, steps, phase) {
  const [t1, t2] = cell._basis;
  const points = [];
  const breathing = 1 + Math.sin(phase * 0.42 + cell.phase) * 0.08;
  const angular = cell.size * breathing;
  for (let i = 0; i < steps; i += 1) {
    const a = (Math.PI * 2 * i) / steps;
    const wobble = 1 + Math.sin(a * 3 + cell.phase) * 0.10;
    const local = angular * wobble;
    const rim = normalize(add(
      mul(cell._dir, Math.cos(local)),
      add(mul(t1, Math.cos(a) * Math.sin(local)), mul(t2, Math.sin(a) * Math.sin(local))),
    ));
    points.push(mul(rim, 1.075 + Math.sin(phase * 0.30 + cell.phase) * 0.004));
  }
  return points;
}

function drawPotentialSubstrate(phase, quality) {
  const fast = quality === "fast";
  const cells = fast ? potentialCells.filter((_, index) => index % 2 === 0) : potentialCells;
  const sorted = [...cells].sort((a, b) => project(a._dir).z - project(b._dir).z);
  for (const cell of sorted) {
    const depth = project(cell._dir).z;
    const visibleAlpha = depth > -0.85 ? cell.alpha : cell.alpha * 0.22;
    const points = potentialCellPolygon(cell, fast ? 8 : 12, phase);
    fillPotentialPolygon(points, cell.color, visibleAlpha);
  }
}

function registerInteractive(type, item, radius) {
  const p = project(mul(direction(item), radius));
  if (p.z < -1.12) return;
  interactivePoints.push({
    type,
    item,
    p,
    hitRadius: Math.max(30, 22 + (item.area || item.weight || 0.08) * 150),
  });
}

function drawFacetMarks(region, phase, quality) {
  if (quality === "fast") return;
  for (const facet of (region._facets || region.facets || []).slice(0, 3)) {
    const facetDir = facet._dir || directionFromAngles(facet.theta, facet.phi);
    const front = project(mul(facetDir, 1)).z > -0.70;
    if (!front) continue;
    const points = [];
    const start = direction(region);
    for (let i = 0; i <= 20; i += 1) {
      const mix = i / 20;
      const blended = normalize(add(mul(start, 1 - mix), mul(facetDir, mix)));
      const pulse = Math.sin(phase * 1.1 + i * 0.3 + facet.theta) * 0.012;
      points.push(mul(blended, 1.18 + region.height * 0.15 + facet.height * 0.08 + pulse));
    }
    drawPath(points, region.color, 0.10 + facet.weight * 0.11, 0.7 + facet.weight * 1.1);
  }
}

function drawRegions(phase, quality) {
  const fast = quality === "fast";
  const regions = [...(data.model.regions || [])]
    .sort((a, b) => project(mul(direction(a), 1)).z - project(mul(direction(b), 1)).z);
  for (const region of regions) {
    const depth = project(mul(direction(region), 1)).z;
    const front = depth > -0.95;
    const alpha = front ? 0.13 + region.area * 1.04 : 0.025;
    const lineAlpha = front ? 0.18 + region.stability * 0.32 : 0.045;
    const points = patchPolygon(region, 1.13, 0.86, fast ? 30 : 52, phase, quality);
    fillProjectedPolygon(points, region.color, alpha, lineAlpha, 0.85 + region.boundary_width * 1.35);
    if (front && region.area > 0.025) drawFacetMarks(region, phase, quality);
    if (front) registerInteractive("region", region, 1.22 + Math.max(region.height, 0) * 0.22);
  }
}

function drawConfidenceModes(phase, quality) {
  const fast = quality === "fast";
  const modes = data.model.confidence_modes || [];
  for (const mode of modes) {
    const dir = direction(mode);
    const depth = project(mul(dir, 1)).z;
    const front = depth > -0.82;
    if (!front) continue;
    const points = patchPolygon(mode, 1.20, 0.48, fast ? 24 : 40, phase, quality);
    const alpha = mode.shadow ? 0.08 + mode.area * 0.34 : 0.11 + mode.health * 0.15;
    fillProjectedPolygon(points, mode.color, alpha, mode.shadow ? 0.26 : 0.20, 0.9 + mode.roughness * 1.9);

    const center = project(mul(dir, 1.32 + mode.height * 0.16));
    ctx.beginPath();
    ctx.arc(center.x, center.y, 3.8 + mode.area * 46, 0, Math.PI * 2);
    ctx.strokeStyle = withAlpha(mode.color, mode.shadow ? 0.28 : 0.22);
    ctx.lineWidth = 1;
    ctx.stroke();
    registerInteractive("confidence", mode, 1.28 + mode.height * 0.16);
  }
}

function drawCutPlane(phase) {
  const center = project(v(0, 0, 0));
  const r = Math.abs(project(v(1.12, 0, 0)).x - center.x);
  ctx.save();
  ctx.translate(center.x, center.y);
  ctx.rotate(-0.32 + Math.sin(phase * 0.36) * 0.025);
  const g = ctx.createLinearGradient(-r, 0, r, 0);
  g.addColorStop(0, "rgba(232, 220, 184, 0)");
  g.addColorStop(0.47, "rgba(232, 220, 184, 0.045)");
  g.addColorStop(0.50, "rgba(232, 220, 184, 0.13)");
  g.addColorStop(0.53, "rgba(232, 220, 184, 0.045)");
  g.addColorStop(1, "rgba(232, 220, 184, 0)");
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.ellipse(0, 0, r * 0.22, r * 1.02, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawGrowthPath() {
  if (!showGrowthPath) return;
  const latest = data.latest_growth;
  if (!latest || !latest.visible_delta || latest.visible_delta.length < 1) return;
  const lookup = Object.fromEntries([
    ...(data.model.regions || []).map((item) => [item.id, item]),
    ...(data.model.anchors || []).map((item) => [item.id, item]),
  ]);
  const points = [];
  for (const item of latest.visible_delta.slice(0, 4)) {
    const target = lookup[item.anchor] || data.model.dominant_region;
    if (!target) continue;
    const dir = direction(target);
    const radius = 1.45 + Math.abs(item.delta) * 8;
    points.push(mul(dir, radius));
  }
  if (points.length === 1) {
    const base = normalize(points[0]);
    points.unshift(v(base.y * 0.36, base.z * 0.36, base.x * 0.36));
  }
  drawPath(points, "#c8954b", 0.42, 1.8);
}

function findNearestInteractive() {
  let best = null;
  let bestDistance = Infinity;
  for (const point of interactivePoints) {
    const distance = Math.hypot(pointer.x - point.p.x, pointer.y - point.p.y);
    if (distance < point.hitRadius && distance < bestDistance) {
      best = point;
      bestDistance = distance;
    }
  }
  return best;
}

function createLabel(item, p, className) {
  const label = document.createElement("div");
  label.className = className;
  label.textContent = item.label;
  label.style.left = `${p.x}px`;
  label.style.top = `${p.y}px`;
  label.style.opacity = p.z > -1.30 ? "1" : "0.22";
  labelLayer.appendChild(label);
}

function addAllLabels() {
  for (const region of (data.model.regions || []).slice(0, 8)) {
    const p = project(mul(direction(region), 1.50 + region.height * 0.22));
    if (p.z > -0.92) createLabel(region, p, "kernel-label");
  }
  for (const mode of (data.model.confidence_modes || []).slice(0, 4)) {
    const p = project(mul(direction(mode), 1.40 + mode.height * 0.18));
    if (p.z > -0.82) createLabel(mode, p, "kernel-label confidence-label");
  }
}

function tooltipHtml(target) {
  const item = target.item;
  const isRegion = target.type === "region";
  const facets = isRegion
    ? (item.facets || [])
      .slice(0, 3)
      .map((facet) => `<span>${facet.label} ${Math.round(facet.weight * 100)}%</span>`)
      .join("")
    : "";
  const subtitle = isRegion ? item.action_label : "confidence form";
  const metrics = isRegion
    ? `
      <div><span>area</span><strong>${Math.round(item.area * 100)}%</strong></div>
      <div><span>height</span><strong>${item.height.toFixed(2)}</strong></div>
      <div><span>curvature</span><strong>${item.roughness.toFixed(2)}</strong></div>
      <div><span>force</span><strong>${item.force.toFixed(2)}</strong></div>
    `
    : `
      <div><span>weight</span><strong>${Math.round(item.area * 100)}%</strong></div>
      <div><span>height</span><strong>${item.height.toFixed(2)}</strong></div>
      <div><span>stability</span><strong>${item.stability.toFixed(2)}</strong></div>
      <div><span>roughness</span><strong>${item.roughness.toFixed(2)}</strong></div>
    `;
  return `
    <div class="hover-title">
      <i style="background:${item.color}"></i>
      <div><strong>${item.label}</strong><span>${subtitle}</span></div>
    </div>
    <div class="hover-metrics">${metrics}</div>
    ${facets ? `<div class="facet-row">${facets}</div>` : ""}
  `;
}

function renderOverlays(quality) {
  if (quality === "fast") {
    if (labelLayer.childNodes.length) labelLayer.innerHTML = "";
    return;
  }
  labelLayer.innerHTML = "";
  hovered = findNearestInteractive();
  if (labelMode === "all") addAllLabels();
  if (labelMode === "off") return;

  const target = selected || hovered;
  if (!target) return;
  const card = document.createElement("div");
  card.className = "hover-card";
  card.innerHTML = tooltipHtml(target);
  const x = Math.min(width - 252, Math.max(18, target.p.x + 16));
  const y = Math.min(height - 178, Math.max(18, target.p.y - 70));
  card.style.left = `${x}px`;
  card.style.top = `${y}px`;
  labelLayer.appendChild(card);
}

function draw(phase, quality) {
  ctx.clearRect(0, 0, width, height);
  if (!data) return;
  interactivePoints = [];
  ctx.save();
  drawBaseLayers(phase, quality);
  drawPotentialSubstrate(phase, quality);
  drawRegions(phase, quality);
  drawConfidenceModes(phase, quality);
  drawCutPlane(phase);
  drawGrowthPath();
  ctx.restore();
  renderOverlays(quality);
}

function formatHeadline(latest) {
  if (!latest || !latest.visible_delta || latest.visible_delta.length === 0) {
    return "waiting for growth signal";
  }
  const top = latest.visible_delta[0];
  const directionText = top.delta >= 0 ? "expanded" : "contracted";
  return `${top.label} ${directionText} ${Math.abs(top.delta).toFixed(3)}`;
}

function renderRegionRows(nextData) {
  const anchorList = document.getElementById("anchorList");
  anchorList.innerHTML = "";
  const regionTitle = document.createElement("div");
  regionTitle.className = "micro-title";
  regionTitle.textContent = "Dominant territories";
  anchorList.appendChild(regionTitle);

  for (const region of (nextData.model.regions || []).slice(0, 8)) {
    const row = document.createElement("div");
    row.className = "anchor-row";
    row.innerHTML = `
      <i class="swatch" style="background:${region.color}"></i>
      <span>${region.label}</span>
      <strong>${Math.round(region.area * 100)}%</strong>
    `;
    anchorList.appendChild(row);
  }

  const confidenceTitle = document.createElement("div");
  confidenceTitle.className = "micro-title confidence-title";
  confidenceTitle.textContent = "Confidence spectrum";
  anchorList.appendChild(confidenceTitle);

  for (const mode of (nextData.model.confidence_modes || []).slice(0, 5)) {
    const row = document.createElement("div");
    row.className = "anchor-row";
    row.innerHTML = `
      <i class="swatch" style="background:${mode.color}"></i>
      <span>${mode.label}</span>
      <strong>${Math.round(mode.area * 100)}%</strong>
    `;
    anchorList.appendChild(row);
  }
}

function renderInfo(nextData) {
  document.getElementById("agentName").textContent = nextData.agent.name;
  document.getElementById("agentType").textContent = nextData.agent.type_label;
  document.getElementById("stage").textContent = nextData.agent.stage;
  document.getElementById("count").textContent = nextData.agent.interaction_count;
  document.getElementById("protoCount").textContent = nextData.prototype_count;
  renderRegionRows(nextData);

  const latest = nextData.latest_growth;
  document.getElementById("growthHeadline").textContent = formatHeadline(latest);

  const timeline = document.getElementById("timeline");
  timeline.innerHTML = "";
  const recent = nextData.recent_growth || [];
  for (let i = 0; i < Math.max(8, recent.length); i += 1) {
    const dot = document.createElement("span");
    dot.className = `timeline-dot ${i === Math.max(8, recent.length) - 1 ? "active" : ""}`;
    timeline.appendChild(dot);
  }

  const growth = document.getElementById("growth");
  if (!latest) {
    growth.innerHTML = '<p class="muted">No growth trace yet.</p>';
    return;
  }
  const dominant = nextData.model.dominant_region;
  const confidence = nextData.model.dominant_confidence;
  const tags = (latest.compressed_tags || []).map((tag) => `<span class="tag">${tag}</span>`).join("");
  const deltas = (latest.visible_delta || [])
    .slice(0, 4)
    .map((item) => `<div class="delta"><span>${item.label}</span><strong>${item.delta > 0 ? "+" : ""}${item.delta.toFixed(3)}</strong></div>`)
    .join("");
  growth.innerHTML = `
    <p class="muted">Latest force changed the visible body; raw text is compressed into tags and deltas.</p>
    <div class="tags">${tags}</div>
    <div class="delta-list">${deltas || '<p class="muted">No visible delta.</p>'}</div>
    <p class="muted compact-note">Dominant: ${dominant ? dominant.label : "unknown"} / ${confidence ? confidence.label : "unknown"}</p>
  `;
}

async function loadData() {
  const response = await fetch("./pkm_visible.json", { cache: "no-store" });
  data = await response.json();
  hydrateModel(data);
  renderInfo(data);
}

function animate(time) {
  requestAnimationFrame(animate);
  const quality = dragging || time - lastInteractionAt < 180 ? "fast" : "high";
  const frameInterval = quality === "fast" ? 16 : 33;
  if (time - lastFrameAt < frameInterval) return;
  lastFrameAt = time;
  const phase = time * 0.001;
  if (!dragging) yaw += 0.00115;
  draw(phase, quality);
}

function setLabelMode(nextMode) {
  labelMode = nextMode;
  selected = null;
  document.querySelectorAll("[data-label-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.labelMode === nextMode);
  });
}

function setGrowthPath(nextValue) {
  showGrowthPath = nextValue;
  const button = document.querySelector("[data-path-toggle]");
  if (!button) return;
  button.classList.toggle("active", showGrowthPath);
  button.textContent = showGrowthPath ? "Growth path on" : "Growth path off";
}

document.querySelectorAll("[data-label-mode]").forEach((button) => {
  button.addEventListener("click", () => setLabelMode(button.dataset.labelMode));
});

const pathToggle = document.querySelector("[data-path-toggle]");
if (pathToggle) {
  pathToggle.addEventListener("click", () => setGrowthPath(!showGrowthPath));
}

mount.addEventListener("pointerdown", (event) => {
  dragging = true;
  lastInteractionAt = performance.now();
  selected = null;
  pointer = { x: event.offsetX, y: event.offsetY };
  lastX = event.clientX;
  lastY = event.clientY;
  downX = event.clientX;
  downY = event.clientY;
  mount.setPointerCapture(event.pointerId);
});

mount.addEventListener("pointermove", (event) => {
  pointer = { x: event.offsetX, y: event.offsetY };
  if (!dragging) return;
  lastInteractionAt = performance.now();
  const dx = event.clientX - lastX;
  const dy = event.clientY - lastY;
  lastX = event.clientX;
  lastY = event.clientY;
  yaw += dx * 0.0055;
  pitch = Math.max(-0.78, Math.min(0.78, pitch + dy * 0.0038));
});

mount.addEventListener("pointerup", (event) => {
  dragging = false;
  lastInteractionAt = performance.now();
  pointer = { x: event.offsetX, y: event.offsetY };
  const moved = Math.hypot(event.clientX - downX, event.clientY - downY);
  if (moved < 7 && labelMode !== "off") selected = findNearestInteractive();
  mount.releasePointerCapture(event.pointerId);
});

mount.addEventListener("pointerleave", () => {
  if (!dragging) pointer = { x: -9999, y: -9999 };
});

mount.addEventListener("wheel", (event) => {
  event.preventDefault();
  lastInteractionAt = performance.now();
  zoom = Math.max(0.78, Math.min(1.32, zoom - event.deltaY * 0.00075));
}, { passive: false });

window.addEventListener("resize", () => {
  resize();
  draw(0, "fast");
});

resize();
setLabelMode("hover");
setGrowthPath(false);
loadData().catch((error) => {
  document.getElementById("growth").innerHTML = `<p class="muted">Failed to load PKM visible data: ${error.message}</p>`;
});
requestAnimationFrame(animate);
