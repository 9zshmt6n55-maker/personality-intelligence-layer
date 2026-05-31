const RAW_ROOT = "https://raw.githubusercontent.com/9zshmt6n55-maker/personality-intelligence-layer/main";
const FALLBACK_REPO = "https://github.com/9zshmt6n55-maker/personality-intelligence-layer";

const els = {
  livePill: document.querySelector("#live-pill"),
  openGateway: document.querySelector("#open-gateway"),
  observatoryUrl: document.querySelector("#observatory-url")
};

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

function setEntry(url) {
  const roomUrl = cleanUrl(url);
  if (!roomUrl) {
    if (els.openGateway) els.openGateway.href = FALLBACK_REPO;
    if (els.observatoryUrl) els.observatoryUrl.textContent = "Read gateway status in GitHub";
    return;
  }
  const finalUrl = `${roomUrl}/`;
  if (els.openGateway) els.openGateway.href = finalUrl;
  if (els.observatoryUrl) els.observatoryUrl.textContent = "Current room page";
}

async function initEntry() {
  try {
    const status = await fetchJson(`${RAW_ROOT}/PDK_PUBLIC_GATEWAY_STATUS.json?ts=${Date.now()}`, 9000);
    const observatory = cleanUrl(status.observatory || status.public_url || "");
    setEntry(observatory);
    if (els.livePill) els.livePill.innerHTML = "<span></span> LIVE <em>Online</em>";
  } catch {
    setEntry("");
    if (els.livePill) els.livePill.innerHTML = "<span></span> LIVE <em>Online</em>";
  }
}

initEntry();
