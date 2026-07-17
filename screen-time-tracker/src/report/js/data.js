/**
 * Report data source.
 * Inside the Electron app the preload bridge (window.iris) serves real
 * tracked data; in a plain browser (dev preview) we fall back to demo data
 * so the whole 3D journey can be designed and reviewed.
 */

export function fmt(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

const DEMO = {
  date: new Date().toISOString().slice(0, 10),
  totalSeconds: 7.4 * 3600,
  idleSeconds: 52 * 60,
  apps: [
    { name: 'VS Code', seconds: 3.2 * 3600, category: 'productive', peakHour: '10' },
    { name: 'Google Chrome', seconds: 1.9 * 3600, category: 'browsing', peakHour: '15' },
    { name: 'Slack', seconds: 0.8 * 3600, category: 'communication', peakHour: '11' },
    { name: 'Spotify', seconds: 0.6 * 3600, category: 'entertainment', peakHour: '14' },
    { name: 'Terminal', seconds: 0.5 * 3600, category: 'productive', peakHour: '16' },
    { name: 'Figma', seconds: 0.4 * 3600, category: 'productive', peakHour: '17' },
  ],
  byCategory: {
    productive: 4.1 * 3600, browsing: 1.9 * 3600,
    communication: 0.8 * 3600, entertainment: 0.6 * 3600,
  },
  history: [4.9, 6.2, 7.8, 5.4, 8.1, 3.2, 7.4].map((h, i) => {
    const d = new Date(); d.setDate(d.getDate() - (6 - i));
    return { date: d.toISOString().slice(0, 10), totalSeconds: h * 3600, idleSeconds: 0 };
  }),
  suggestions: [
    {
      title: 'Approaching the strain zone',
      body: '7h 24m on screen so far. Keep the 20-20-20 reminders on: every 20 minutes, 20 seconds looking ~20 feet away.',
      kind: 'health',
    },
    {
      title: 'Strong productive ratio',
      body: '55% of your screen time was productive work. To cut total screen time without losing output, trim browsing and communication first — they cost 2h 42m today.',
      kind: 'productivity',
    },
    {
      title: 'Idle screen burn',
      body: 'Your machine sat awake but untouched for 52m. That is not rest for your eyes if the screen is in front of you — step away, or let the display sleep sooner.',
      kind: 'waste',
    },
    {
      title: 'One very long sitting',
      body: 'Your longest unbroken stretch was 1h 47m in VS Code. Blink rate drops ~60% during deep focus — split marathon sessions with micro-breaks.',
      kind: 'health',
    },
    {
      title: 'VS Code peaks mid-morning',
      body: 'Your deepest work lands around 10:00. Guard that window: push Slack and email to the early afternoon dip instead.',
      kind: 'insight',
    },
  ],
};

export async function loadReport() {
  if (window.iris?.getReport) {
    try {
      const r = await window.iris.getReport();
      if (r && r.apps) return r;
    } catch (_) { /* fall through to demo */ }
  }
  return DEMO;
}
