/**
 * Turns raw store data into the schema the 3D report page renders:
 * per-app bubbles for the optic nerve and suggestion cards for the brain.
 */

const CATEGORIES = {
  productive: ['VS Code', 'IntelliJ IDEA', 'PyCharm', 'Visual Studio', 'Terminal', 'Word',
    'Excel', 'PowerPoint', 'Figma', 'Blender', 'Obsidian', 'Notion'],
  communication: ['Slack', 'Microsoft Teams', 'Outlook', 'Discord', 'Zoom', 'Thunderbird'],
  browsing: ['Google Chrome', 'Firefox', 'Microsoft Edge', 'Safari', 'Brave'],
  entertainment: ['Spotify', 'YouTube', 'Netflix', 'Steam', 'VLC', 'mpv'],
};

function categoryOf(app) {
  for (const [cat, list] of Object.entries(CATEGORIES)) {
    if (list.some((n) => app.toLowerCase().includes(n.toLowerCase()))) return cat;
  }
  return 'other';
}

function hms(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function buildReport(raw) {
  const apps = Object.entries(raw.apps)
    .map(([name, e]) => ({
      name,
      seconds: e.total,
      category: categoryOf(name),
      peakHour: Object.entries(e.hours).sort((a, b) => b[1] - a[1])[0]?.[0] ?? null,
    }))
    .sort((a, b) => b.seconds - a.seconds);

  const totalSeconds = apps.reduce((a, e) => a + e.seconds, 0);

  const byCategory = {};
  for (const a of apps) byCategory[a.category] = (byCategory[a.category] || 0) + a.seconds;

  const longest = (raw.sessions || [])
    .map((s) => ({ ...s, dur: s.end - s.start }))
    .sort((a, b) => b.dur - a.dur)[0] || null;

  const lateNightSeconds = apps.reduce((acc, a) => {
    const e = raw.apps[a.name];
    for (const [h, sec] of Object.entries(e.hours)) {
      const hour = Number(h);
      if (hour >= 22 || hour < 5) acc += sec;
    }
    return acc;
  }, 0);

  return {
    date: raw.date,
    totalSeconds,
    idleSeconds: raw.idleSeconds,
    apps,
    byCategory,
    history: raw.history || [],
    suggestions: buildSuggestions({ apps, totalSeconds, byCategory, raw, longest, lateNightSeconds }),
  };
}

function buildSuggestions({ apps, totalSeconds, byCategory, raw, longest, lateNightSeconds }) {
  const s = [];
  const prod = byCategory.productive || 0;
  const fun = (byCategory.entertainment || 0) + (byCategory.browsing || 0) * 0.5;

  if (totalSeconds === 0) {
    s.push({
      title: 'No screen time recorded yet',
      body: 'Leave Iris running in the background and this brain will start thinking. Come back after a few hours of normal use.',
      kind: 'info',
    });
    return s;
  }

  if (totalSeconds > 8 * 3600) {
    s.push({
      title: 'Heavy screen day',
      body: `You have logged ${hms(totalSeconds)} today. Past the 8-hour mark, dry eyes and fatigue climb fast — plan a hard stop or a long off-screen break this evening.`,
      kind: 'health',
    });
  } else if (totalSeconds > 5 * 3600) {
    s.push({
      title: 'Approaching the strain zone',
      body: `${hms(totalSeconds)} on screen so far. Keep the 20-20-20 reminders on: every 20 minutes, 20 seconds looking ~20 feet away.`,
      kind: 'health',
    });
  } else {
    s.push({
      title: 'Healthy pace so far',
      body: `Only ${hms(totalSeconds)} of screen time today — your eyes thank you. Keep breaks regular even on light days.`,
      kind: 'health',
    });
  }

  if (longest && longest.dur > 90 * 60) {
    s.push({
      title: 'One very long sitting',
      body: `Your longest unbroken stretch was ${hms(longest.dur)} in ${longest.app}. Blink rate drops ~60% during focus like this — split marathon sessions with micro-breaks.`,
      kind: 'health',
    });
  }

  if (prod > 0 && prod / totalSeconds >= 0.6) {
    s.push({
      title: 'Strong productive ratio',
      body: `${Math.round((prod / totalSeconds) * 100)}% of your screen time was productive work. To cut total screen time without losing output, trim browsing and communication first — they cost ${hms((byCategory.browsing || 0) + (byCategory.communication || 0))} today.`,
      kind: 'productivity',
    });
  } else if (fun > prod) {
    s.push({
      title: 'Leisure is leading',
      body: `Entertainment and browsing (${hms((byCategory.entertainment || 0) + (byCategory.browsing || 0))}) outweigh focused work (${hms(prod)}). If that was intentional rest, great — if not, try a 45-minute focus block with the widget's tracking toggle as your commitment switch.`,
      kind: 'productivity',
    });
  }

  if (raw.idleSeconds > 45 * 60) {
    s.push({
      title: 'Idle screen burn',
      body: `Your machine sat awake but untouched for ${hms(raw.idleSeconds)}. That is not rest for your eyes if the screen is in front of you — step away, or let the display sleep sooner.`,
      kind: 'waste',
    });
  }

  if (lateNightSeconds > 30 * 60) {
    s.push({
      title: 'Late-night glow',
      body: `${hms(lateNightSeconds)} of use between 22:00 and 05:00. Blue light this late pushes sleep back — enable night mode, or better, close the lid.`,
      kind: 'health',
    });
  }

  const top = apps[0];
  if (top && top.seconds / totalSeconds > 0.5) {
    s.push({
      title: `${top.name} dominates your day`,
      body: `${Math.round((top.seconds / totalSeconds) * 100)}% of screen time went to ${top.name}${top.peakHour !== null ? `, peaking around ${top.peakHour}:00` : ''}. Ask whether that share matches its value to you.`,
      kind: 'insight',
    });
  }

  return s.slice(0, 5);
}

module.exports = { buildReport, categoryOf, CATEGORIES };
