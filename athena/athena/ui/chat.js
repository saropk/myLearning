/* Aegis chat client — phase 1.
 *
 * Talks to /api/chat and /api/events on the daemon. No framework, no build step
 * (ATHENA.md, Conventions). The bearer token arrives once in the launch URL's ?token=,
 * is kept in sessionStorage, and is scrubbed from the address bar so it does not sit in
 * history or get pasted into a screenshot.
 */
"use strict";

const TOKEN_KEY = "athena.token";

function resolveToken() {
  const fromUrl = new URLSearchParams(location.search).get("token");
  if (fromUrl) {
    sessionStorage.setItem(TOKEN_KEY, fromUrl);
    history.replaceState(null, "", location.pathname);
    return fromUrl;
  }
  return sessionStorage.getItem(TOKEN_KEY);
}

const token = resolveToken();

const el = (id) => document.getElementById(id);
const log = el("log");
const emblem = el("emblem");

/* Valve tints, straight from the spec's state-reactive table. */
const VALVE = {
  0: { halo: "rgb(112,20,10)", engraving: "rgb(195,75,55)", intensity: 0.38, label: "0 Sealed" },
  1: { halo: "rgb(205,78,32)", engraving: "rgb(255,178,118)", intensity: 0.85, label: "1 Questions" },
  2: { halo: "rgb(236,128,58)", engraving: "rgb(255,205,150)", intensity: 1.0, label: "2 Redacted" },
  3: { halo: "rgb(255,178,84)", engraving: "rgb(255,228,178)", intensity: 1.15, label: "3 Open" },
};

/* DORMANT slow and dim, ACTIVE ~1.6x faster, SERIOUS tighter and white-hot. */
const STATE_LOOK = {
  DORMANT: { spin: "44s", scale: 0.92, brightness: 0.55 },
  ACTIVE: { spin: "26s", scale: 1.0, brightness: 1.0 },
  SERIOUS: { spin: "18s", scale: 0.9, brightness: 1.25 },
};

function addMessage(kind, text, tag) {
  if (!text) return;
  const node = document.createElement("div");
  node.className = `msg ${kind}`;
  if (tag) {
    const label = document.createElement("span");
    label.className = "tag";
    label.textContent = tag;
    node.appendChild(label);
  }
  node.appendChild(document.createTextNode(text));
  log.appendChild(node);
  log.scrollTop = log.scrollHeight;
}

function applySnapshot(s) {
  el("c-state").textContent = s.state;
  const valve = VALVE[s.valve] || VALVE[1];
  el("c-valve").textContent = valve.label;
  el("valve-select").value = String(s.valve);
  el("c-mic").textContent = s.mic_open ? "open" : "closed";
  el("c-mic-chip").classList.toggle("mic-open", Boolean(s.mic_open));

  const look = STATE_LOOK[s.state] || STATE_LOOK.ACTIVE;
  const root = document.documentElement.style;
  root.setProperty("--halo", valve.halo);
  root.setProperty("--engraving", valve.engraving);
  root.setProperty("--intensity", String(valve.intensity * look.brightness));
  root.setProperty("--spin", look.spin);
  emblem.style.transform = `scale(${look.scale})`;
  emblem.dataset.speaking = String(Boolean(s.speaking));
}

async function api(path, options = {}) {
  const headers = Object.assign({ Authorization: `Bearer ${token}` }, options.headers || {});
  if (options.body) headers["Content-Type"] = "application/json";
  const res = await fetch(path, Object.assign({}, options, { headers }));
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

/* --- live state ------------------------------------------------------------------ */
function connectEvents() {
  // EventSource cannot set headers, so the token rides in the query string. Same secret.
  const stream = new EventSource(`/api/events?token=${encodeURIComponent(token)}`);
  stream.addEventListener("state", (e) => applySnapshot(JSON.parse(e.data)));
  stream.addEventListener("notice", (e) => addMessage("notice", JSON.parse(e.data).text));
  stream.onerror = () => {
    /* EventSource retries on its own; nothing to do but let it. */
  };
}

/* --- chat ------------------------------------------------------------------------ */
el("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = el("input");
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  addMessage("user", message);
  el("send").disabled = true;
  try {
    const data = await api("/api/chat", { method: "POST", body: JSON.stringify({ message }) });
    applySnapshot(data);
    if (data.route === "overheard") {
      addMessage("notice", "(not directed at Athena — kept as context only)");
    } else {
      addMessage("athena", data.reply, data.route === "answer" ? null : data.route);
    }
    if (data.error) addMessage("error", data.error);
  } catch (err) {
    addMessage("error", String(err.message || err));
  } finally {
    el("send").disabled = false;
    input.focus();
  }
});

el("valve-select").addEventListener("change", async (event) => {
  const level = Number(event.target.value);
  try {
    await api("/api/valve", { method: "POST", body: JSON.stringify({ level }) });
  } catch (err) {
    addMessage("error", String(err.message || err));
  }
});

/* --- status panel ---------------------------------------------------------------- */
let statusTimer = null;

async function refreshStatus() {
  try {
    const s = await api("/api/status");
    el("c-brain").textContent = s.brain.reachable ? s.brain.model : "unreachable";
    const ram = s.ram;
    el("c-ram").textContent = `${ram.total_gb.toFixed(2)}/${ram.budget_gb} GB`;
    el("c-ram").style.color = ram.within_budget ? "" : "#d9704f";
    if (el("panel").classList.contains("open")) {
      el("panel-body").textContent = JSON.stringify(s, null, 2);
    }
  } catch (err) {
    el("c-brain").textContent = "?";
  }
}

el("toggle-panel").addEventListener("click", () => {
  el("panel").classList.toggle("open");
  refreshStatus();
});

/* --- boot ------------------------------------------------------------------------ */
if (!token) {
  addMessage(
    "error",
    "No API token. Start the daemon with `python -m athena` and open the URL it prints " +
      "(it carries ?token=…)."
  );
} else {
  api("/api/state").then(applySnapshot).catch((err) => addMessage("error", String(err.message)));
  connectEvents();
  refreshStatus();
  statusTimer = setInterval(refreshStatus, 5000);
  window.addEventListener("beforeunload", () => clearInterval(statusTimer));
}
