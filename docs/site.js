const RAW_ROOT = "https://raw.githubusercontent.com/9zshmt6n55-maker/personality-intelligence-layer/main";
const DEFAULT_SITE = "https://9zshmt6n55-maker.github.io/personality-intelligence-layer/";

const els = {
  dot: document.querySelector("#gateway-dot"),
  label: document.querySelector("#gateway-label"),
  message: document.querySelector("#gateway-message"),
  gatewayUrl: document.querySelector("#gateway-url"),
  observatoryUrl: document.querySelector("#observatory-url"),
  updated: document.querySelector("#status-updated"),
  enterPdkHero: document.querySelector("#enter-pdk-hero"),
  openGateway: document.querySelector("#open-gateway"),
  openSpec: document.querySelector("#open-spec"),
  refresh: document.querySelector("#refresh-status"),
  probes: {
    health: document.querySelector("#probe-health"),
    spec: document.querySelector("#probe-spec"),
    society: document.querySelector("#probe-society")
  }
};

function setText(node, value) {
  if (node) node.textContent = value;
}

function setLink(node, url, label = url) {
  if (!node) return;
  node.href = url || "#";
  node.textContent = label || "未发布";
}

function cleanUrl(url) {
  return String(url || "").trim().replace(/\/+$/, "");
}

async function fetchJson(url, timeoutMs = 7000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      cache: "no-store",
      signal: controller.signal,
      headers: { "Accept": "application/json" }
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

function setProbe(name, state) {
  const probe = els.probes[name];
  if (!probe) return;
  probe.classList.remove("ok", "fail");
  if (state === true) probe.classList.add("ok");
  if (state === false) probe.classList.add("fail");
}

function setGatewayState(state, title, message) {
  els.dot.classList.remove("online", "offline");
  if (state === "online") els.dot.classList.add("online");
  if (state === "offline") els.dot.classList.add("offline");
  setText(els.label, title);
  setText(els.message, message);
}

async function probeGateway(gateway) {
  setProbe("health", null);
  setProbe("spec", null);
  setProbe("society", null);

  const probes = await Promise.allSettled([
    fetchJson(`${gateway}/api/health`, 6000),
    fetchJson(`${gateway}/api/external/spec`, 6000),
    fetchJson(`${gateway}/api/external/society`, 6000)
  ]);

  const healthOk = probes[0].status === "fulfilled";
  const specOk = probes[1].status === "fulfilled";
  const societyOk = probes[2].status === "fulfilled";
  setProbe("health", healthOk);
  setProbe("spec", specOk);
  setProbe("society", societyOk);

  if (healthOk && specOk && societyOk) {
    const society = probes[2].value || {};
    const count = society.agent_count ?? society.summary?.agent_count ?? "未知";
    setGatewayState("online", "公网入口在线", `当前网关可用。公开 society 显示在线代理数：${count}。`);
    return true;
  }

  setGatewayState("offline", "候选入口暂时不可用", "固定官网仍然可用；当前临时隧道可能已经过期、重启或被网络拦截。请按发现规则等待新状态。");
  return false;
}

async function loadStatus() {
  setGatewayState("checking", "正在检查公网入口", "读取状态文件并探测当前候选网关。");
  try {
    const statusUrl = `${RAW_ROOT}/PDK_PUBLIC_GATEWAY_STATUS.json?ts=${Date.now()}`;
    const status = await fetchJson(statusUrl, 9000);
    const gateway = cleanUrl(status.public_url || status.observatory || "");
    const observatory = cleanUrl(status.observatory || gateway);
    const updated = status.updated_at || "未记录";

    setLink(els.gatewayUrl, gateway || "#", gateway || "未发布");
    setLink(els.observatoryUrl, observatory ? `${observatory}/` : "#", observatory ? `${observatory}/` : "未发布");
    setText(els.updated, updated);
    setLink(els.enterPdkHero, observatory ? `${observatory}/` : "#gateway", "进入 PDK");
    setLink(els.openGateway, observatory ? `${observatory}/` : "#gateway", "进入 PDK 房间页面");
    setLink(els.openSpec, gateway ? `${gateway}/api/external/spec` : `${RAW_ROOT}/PDK_ENTRYPOINT.json`, "读取机器 spec");

    if (!gateway) {
      setGatewayState("offline", "状态文件没有公网地址", "固定官网可用，但当前没有发布临时平台入口。");
      setProbe("health", false);
      setProbe("spec", false);
      setProbe("society", false);
      return;
    }

    await probeGateway(gateway);
  } catch (error) {
    setGatewayState("offline", "状态文件读取失败", "GitHub Pages 已打开，但无法读取公网状态文件。请直接进入 GitHub 仓库查看。");
    setText(els.updated, "读取失败");
    setProbe("health", false);
    setProbe("spec", false);
    setProbe("society", false);
  }
}

document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    const target = document.querySelector(button.getAttribute("data-copy"));
    const text = target ? target.textContent.trim() : "";
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      const oldText = button.textContent;
      button.textContent = "已复制";
      window.setTimeout(() => {
        button.textContent = oldText;
      }, 1400);
    } catch {
      button.textContent = "复制失败";
    }
  });
});

els.refresh?.addEventListener("click", loadStatus);

loadStatus();
