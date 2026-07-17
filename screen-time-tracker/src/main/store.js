/**
 * Usage store: one JSON file per day in the Electron userData directory.
 * Shape:
 * {
 *   date: "2026-07-17",
 *   apps: { "VS Code": { total: 4820, hours: { "9": 1200, "10": 3620 } } },
 *   idleSeconds: 900,
 *   unknownSeconds: 40,
 *   sessions: [ { app, start, end } ]   // contiguous focus sessions
 * }
 */
const fs = require('fs');
const path = require('path');

const SAVE_EVERY_MS = 30 * 1000;
const SESSION_GAP_SECONDS = 30; // focus switches shorter than this merge into one session

function todayKey(d = new Date()) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

class Store {
  constructor(dataDir) {
    this.dataDir = dataDir;
    fs.mkdirSync(dataDir, { recursive: true });
    this.day = this.loadDay(todayKey());
    this.dirty = false;
    this.saveTimer = setInterval(() => this.flush(), SAVE_EVERY_MS);
    this.openSession = null;
  }

  fileFor(dateKey) { return path.join(this.dataDir, `usage-${dateKey}.json`); }

  loadDay(dateKey) {
    try {
      const raw = fs.readFileSync(this.fileFor(dateKey), 'utf8');
      const parsed = JSON.parse(raw);
      if (parsed && parsed.date === dateKey) return parsed;
    } catch (_) { /* first run of the day */ }
    return { date: dateKey, apps: {}, idleSeconds: 0, unknownSeconds: 0, sessions: [] };
  }

  rolloverIfNeeded() {
    const key = todayKey();
    if (this.day.date !== key) {
      this.flush();
      this.day = this.loadDay(key);
      this.openSession = null;
    }
  }

  addUsage(app, seconds) {
    this.rolloverIfNeeded();
    const hour = String(new Date().getHours());
    const entry = this.day.apps[app] || (this.day.apps[app] = { total: 0, hours: {} });
    entry.total += seconds;
    entry.hours[hour] = (entry.hours[hour] || 0) + seconds;
    this.trackSession(app, seconds);
    this.dirty = true;
  }

  trackSession(app, seconds) {
    const now = Date.now() / 1000;
    const s = this.openSession;
    if (s && s.app === app && now - s.end <= SESSION_GAP_SECONDS + seconds) {
      s.end = now;
    } else {
      if (s) this.day.sessions.push({ app: s.app, start: s.start, end: s.end });
      this.openSession = { app, start: now - seconds, end: now };
    }
  }

  addIdle(seconds) {
    this.rolloverIfNeeded();
    this.day.idleSeconds += seconds;
    this.dirty = true;
  }

  addUnknown(seconds) {
    this.rolloverIfNeeded();
    this.day.unknownSeconds += seconds;
    this.dirty = true;
  }

  todaySummary() {
    this.rolloverIfNeeded();
    const total = Object.values(this.day.apps).reduce((a, e) => a + e.total, 0);
    const top = Object.entries(this.day.apps).sort((a, b) => b[1].total - a[1].total)[0];
    return {
      date: this.day.date,
      totalSeconds: total,
      idleSeconds: this.day.idleSeconds,
      topApp: top ? { name: top[0], seconds: top[1].total } : null,
    };
  }

  /** Full day data plus recent history for the report. */
  reportData(historyDays = 7) {
    this.rolloverIfNeeded();
    const history = [];
    for (let i = historyDays - 1; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const key = todayKey(d);
      const day = key === this.day.date ? this.day : this.loadDay(key);
      const total = Object.values(day.apps).reduce((a, e) => a + e.total, 0);
      history.push({ date: key, totalSeconds: total, idleSeconds: day.idleSeconds });
    }
    const sessions = [...this.day.sessions];
    if (this.openSession) sessions.push({ ...this.openSession });
    return { ...this.day, sessions, history };
  }

  flush() {
    if (!this.dirty) return;
    try {
      const data = { ...this.day };
      fs.writeFileSync(this.fileFor(this.day.date), JSON.stringify(data, null, 2));
      this.dirty = false;
    } catch (err) {
      console.error('store flush failed:', err.message);
    }
  }

  dispose() {
    clearInterval(this.saveTimer);
    if (this.openSession) {
      this.day.sessions.push({ ...this.openSession });
      this.openSession = null;
      this.dirty = true;
    }
    this.flush();
  }
}

module.exports = { Store, todayKey };
