/**
 * Active-window tracker.
 * Polls the OS for the focused application, folds the elapsed time into the
 * store, and flags idle time using Electron's powerMonitor.
 * No native dependencies: each platform is queried through built-in shell tools.
 */
const { execFile } = require('child_process');
const os = require('os');

const POLL_SECONDS = 5;
const IDLE_AFTER_SECONDS = 90; // no input for this long => "idle", not app time

function execFileP(cmd, args, options = {}) {
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout: 4000, ...options }, (err, stdout) => {
      resolve(err ? null : stdout.toString().trim());
    });
  });
}

/** Windows: PowerShell + user32 to resolve the foreground window's process. */
const WIN_PS_SCRIPT = `
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class FG {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
}
"@
$h = [FG]::GetForegroundWindow()
$procId = 0
[FG]::GetWindowThreadProcessId($h, [ref]$procId) | Out-Null
if ($procId -ne 0) { (Get-Process -Id $procId -ErrorAction SilentlyContinue).ProcessName }
`;

async function getActiveAppWindows() {
  const out = await execFileP('powershell.exe', [
    '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', WIN_PS_SCRIPT,
  ]);
  return out || null;
}

async function getActiveAppMac() {
  const out = await execFileP('osascript', [
    '-e', 'tell application "System Events" to get name of first application process whose frontmost is true',
  ]);
  return out || null;
}

async function getActiveAppLinux() {
  // X11 first: xdotool, then xprop as fallback.
  const winId = await execFileP('xdotool', ['getactivewindow']);
  if (winId) {
    const cls = await execFileP('xprop', ['-id', winId, 'WM_CLASS']);
    if (cls) {
      const m = cls.match(/"([^"]+)"\s*$/);
      if (m) return m[1];
    }
    const name = await execFileP('xdotool', ['getactivewindow', 'getwindowname']);
    if (name) return name;
  }
  // Wayland/GNOME and others do not expose the focused window generically.
  return null;
}

async function getActiveApp() {
  switch (os.platform()) {
    case 'win32': return getActiveAppWindows();
    case 'darwin': return getActiveAppMac();
    default: return getActiveAppLinux();
  }
}

/** Normalise noisy process names into friendly app names. */
const NAME_MAP = {
  chrome: 'Google Chrome', 'google-chrome': 'Google Chrome', msedge: 'Microsoft Edge',
  firefox: 'Firefox', 'firefox-esr': 'Firefox', code: 'VS Code', 'code - insiders': 'VS Code',
  electron: 'Electron App', explorer: 'Windows Explorer', slack: 'Slack', discord: 'Discord',
  spotify: 'Spotify', 'gnome-terminal-server': 'Terminal', konsole: 'Terminal',
  'org.gnome.nautilus': 'Files', idea64: 'IntelliJ IDEA', pycharm64: 'PyCharm',
  devenv: 'Visual Studio', winword: 'Word', excel: 'Excel', powerpnt: 'PowerPoint',
  olk: 'Outlook', outlook: 'Outlook', teams: 'Microsoft Teams', 'ms-teams': 'Microsoft Teams',
};

function friendlyName(raw) {
  if (!raw) return null;
  const key = raw.toLowerCase().replace(/\.exe$/, '');
  return NAME_MAP[key] || raw.replace(/\.exe$/i, '');
}

class Tracker {
  /**
   * @param {import('./store')} store
   * @param {Electron.PowerMonitor} powerMonitor
   */
  constructor(store, powerMonitor) {
    this.store = store;
    this.powerMonitor = powerMonitor;
    this.enabled = true;
    this.timer = null;
    this.currentApp = null;
    this.listeners = new Set();
  }

  start() {
    if (this.timer) return;
    this.timer = setInterval(() => this.tick().catch(() => {}), POLL_SECONDS * 1000);
  }

  stop() {
    clearInterval(this.timer);
    this.timer = null;
  }

  setEnabled(on) {
    this.enabled = on;
    if (!on) this.currentApp = null;
    this.emit();
  }

  onUpdate(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
  emit() { for (const fn of this.listeners) fn(this.snapshot()); }

  snapshot() {
    return {
      enabled: this.enabled,
      currentApp: this.currentApp,
      today: this.store.todaySummary(),
    };
  }

  async tick() {
    if (!this.enabled) return;
    const idleSec = this.powerMonitor.getSystemIdleTime();
    if (idleSec >= IDLE_AFTER_SECONDS) {
      this.currentApp = null;
      this.store.addIdle(POLL_SECONDS);
    } else {
      const app = friendlyName(await getActiveApp());
      this.currentApp = app;
      if (app) this.store.addUsage(app, POLL_SECONDS);
      else this.store.addUnknown(POLL_SECONDS);
    }
    this.emit();
  }
}

module.exports = { Tracker, POLL_SECONDS };
