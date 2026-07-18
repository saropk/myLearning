/* Plain 2D report. Fetches /api/report and renders. No dependencies. */

const $ = (id) => document.getElementById(id);

function hm(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m`;
}

async function fetchJSON(url) {
  const res = await fetch(url);
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || res.statusText);
  return body;
}

function barRow(name, sub, seconds, maxSeconds, cssClass) {
  const row = document.createElement("div");
  row.className = "bar-row";
  const pct = maxSeconds ? Math.max(1, (seconds / maxSeconds) * 100) : 0;
  row.innerHTML = `
    <span class="name">${name}${sub ? `<small>${sub}</small>` : ""}</span>
    <span class="bar-track"><span class="bar-fill ${cssClass}" style="width:${pct}%"></span></span>
    <span class="time">${hm(seconds)}</span>`;
  return row;
}

function render(report) {
  const hasData = report.totals.activeSeconds + report.totals.idleSeconds > 0;
  $("report").hidden = !hasData;
  $("empty").hidden = hasData;
  if (!hasData) return;

  $("stat-active").textContent = hm(report.totals.activeSeconds);
  $("stat-idle").textContent = hm(report.totals.idleSeconds);
  if (report.longestSession) {
    $("stat-longest").textContent = hm(report.longestSession.seconds);
    $("stat-longest-label").textContent =
      `longest session · ${report.longestSession.appName}`;
  } else {
    $("stat-longest").textContent = "–";
  }

  const sugg = report.suggestions || [];
  $("suggestions-section").hidden = sugg.length === 0;
  $("suggestions").replaceChildren(
    ...sugg.map((s) => {
      const li = document.createElement("li");
      li.className = s.severity;
      li.textContent = s.message;
      return li;
    })
  );

  const maxApp = Math.max(...report.apps.map((a) => a.activeSeconds), 1);
  $("apps").replaceChildren(
    ...report.apps
      .filter((a) => a.activeSeconds >= 60)
      .map((a) =>
        barRow(a.appName, a.category, a.activeSeconds, maxApp,
               `cat-${a.category.replace(/\s/g, "")}`))
  );

  const maxCat = Math.max(...report.categories.map((c) => c.activeSeconds), 1);
  $("categories").replaceChildren(
    ...report.categories.map((c) =>
      barRow(c.category, "", c.activeSeconds, maxCat,
             `cat-${c.category.replace(/\s/g, "")}`))
  );

  const maxHour = Math.max(
    ...report.hourly.map((h) => h.activeSeconds + h.idleSeconds), 1);
  $("hourly").replaceChildren(
    ...report.hourly.map((h) => {
      const cell = document.createElement("div");
      cell.className = "hour";
      cell.title = `${String(h.hour).padStart(2, "0")}:00 — ` +
        `${hm(h.activeSeconds)} active, ${hm(h.idleSeconds)} idle`;
      const idle = document.createElement("div");
      idle.className = "h-idle";
      idle.style.height = `${(h.idleSeconds / maxHour) * 100}%`;
      const active = document.createElement("div");
      active.className = "h-active";
      active.style.height = `${(h.activeSeconds / maxHour) * 100}%`;
      cell.append(idle, active);
      return cell;
    })
  );

  const b = report.breaks;
  $("breaks-section").hidden = b.prompted === 0;
  if (b.prompted > 0) {
    $("breaks").textContent =
      `${b.taken} of ${b.prompted} break prompts taken · ` +
      `${b.skipped} skipped · ${b.snoozed} snoozed`;
  }
}

async function load(day) {
  try {
    $("error").hidden = true;
    render(await fetchJSON(`/api/report?day=${day}`));
    document.querySelectorAll("#day-picker button").forEach((btn) =>
      btn.classList.toggle("active", btn.dataset.day === day));
  } catch (e) {
    $("report").hidden = true;
    $("empty").hidden = true;
    $("error").hidden = false;
    $("error").textContent = `Could not load report: ${e.message}`;
  }
}

async function init() {
  let days = [];
  try {
    days = await fetchJSON("/api/days");
  } catch (e) {
    /* fall through to today */
  }
  if (days.length === 0) days = [new Date().toISOString().slice(0, 10)];

  const requested = new URLSearchParams(location.search).get("day");
  const initial = requested && days.includes(requested) ? requested : days[0];

  $("day-picker").replaceChildren(
    ...days.slice(0, 14).map((day) => {
      const btn = document.createElement("button");
      btn.dataset.day = day;
      btn.textContent = day;
      btn.addEventListener("click", () => load(day));
      return btn;
    })
  );
  load(initial);
}

init();
