const {
  app, BrowserWindow, Tray, Menu, ipcMain, powerMonitor, Notification, screen, nativeImage,
} = require('electron');
const path = require('path');
const { Store } = require('./store');
const { Tracker } = require('./tracker');
const { buildReport } = require('./report-data');

let store;
let tracker;
let widgetWin = null;
let reportWin = null;
let tray = null;

/* ---------------- eye care (20-20-20) ---------------- */
const EYE_BREAK_EVERY_MS = 20 * 60 * 1000;
let eyeCareOn = true;
let eyeTimer = null;
let nextBreakAt = Date.now() + EYE_BREAK_EVERY_MS;

function scheduleEyeBreak() {
  clearTimeout(eyeTimer);
  if (!eyeCareOn) return;
  nextBreakAt = Date.now() + EYE_BREAK_EVERY_MS;
  eyeTimer = setTimeout(() => {
    if (tracker.enabled && Notification.isSupported()) {
      new Notification({
        title: 'Eye break — 20 / 20 / 20',
        body: 'Look at something ~20 feet (6 m) away for 20 seconds. Your optic nerve will send a thank-you note.',
        silent: false,
      }).show();
    }
    widgetWin?.webContents.send('eye-break');
    scheduleEyeBreak();
  }, EYE_BREAK_EVERY_MS);
}

/* ---------------- windows ---------------- */
function createWidget() {
  const { width } = screen.getPrimaryDisplay().workAreaSize;
  widgetWin = new BrowserWindow({
    width: 320,
    height: 190,
    x: width - 340,
    y: 24,
    frame: false,
    transparent: true,
    resizable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, '..', 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  widgetWin.setAlwaysOnTop(true, 'floating');
  widgetWin.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  widgetWin.loadFile(path.join(__dirname, '..', 'widget', 'widget.html'));
  widgetWin.on('closed', () => { widgetWin = null; });
}

function openReport() {
  if (reportWin) { reportWin.focus(); return; }
  reportWin = new BrowserWindow({
    width: 1280,
    height: 820,
    backgroundColor: '#02030a',
    autoHideMenuBar: true,
    title: 'Iris — Screen Time Report',
    webPreferences: {
      preload: path.join(__dirname, '..', 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  reportWin.loadFile(path.join(__dirname, '..', 'report', 'index.html'));
  reportWin.on('closed', () => { reportWin = null; });
}

/* ---------------- tray ---------------- */
function trayIcon() {
  // 16x16 blue dot, generated inline so no asset pipeline is needed.
  const size = 16;
  const buf = Buffer.alloc(size * size * 4);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const dx = x - 7.5, dy = y - 7.5;
      const d = Math.sqrt(dx * dx + dy * dy);
      const i = (y * size + x) * 4;
      const a = Math.max(0, Math.min(1, 7.5 - d));
      buf[i] = 120; buf[i + 1] = 200; buf[i + 2] = 255; buf[i + 3] = Math.round(a * 255);
    }
  }
  return nativeImage.createFromBuffer(buf, { width: size, height: size });
}

function refreshTray() {
  if (!tray) return;
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: tracker.enabled ? 'Pause tracking' : 'Resume tracking', click: () => setTracking(!tracker.enabled) },
    { label: eyeCareOn ? 'Disable eye-care reminders' : 'Enable eye-care reminders', click: () => setEyeCare(!eyeCareOn) },
    { type: 'separator' },
    { label: 'Show widget', click: () => (widgetWin ? widgetWin.show() : createWidget()) },
    { label: 'Open 3D report', click: openReport },
    { type: 'separator' },
    { label: 'Quit Iris', click: () => app.quit() },
  ]));
  tray.setToolTip(`Iris — ${tracker.enabled ? 'tracking' : 'paused'}`);
}

function setTracking(on) {
  tracker.setEnabled(on);
  refreshTray();
}

function setEyeCare(on) {
  eyeCareOn = on;
  scheduleEyeBreak();
  widgetWin?.webContents.send('state', publicState());
  refreshTray();
}

function publicState() {
  return { ...tracker.snapshot(), eyeCareOn, nextBreakAt };
}

/* ---------------- ipc ---------------- */
ipcMain.handle('get-state', () => publicState());
ipcMain.handle('get-report', () => buildReport(store.reportData()));
ipcMain.handle('toggle-tracking', () => { setTracking(!tracker.enabled); return publicState(); });
ipcMain.handle('toggle-eyecare', () => { setEyeCare(!eyeCareOn); return publicState(); });
ipcMain.handle('open-report', () => { openReport(); });
ipcMain.handle('hide-widget', () => { widgetWin?.hide(); });

/* ---------------- lifecycle ---------------- */
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => { widgetWin?.show(); widgetWin?.focus(); });

  app.whenReady().then(() => {
    store = new Store(path.join(app.getPath('userData'), 'data'));
    tracker = new Tracker(store, powerMonitor);
    tracker.start();
    tracker.onUpdate(() => widgetWin?.webContents.send('state', publicState()));

    tray = new Tray(trayIcon());
    refreshTray();
    createWidget();
    scheduleEyeBreak();
  });

  // Keep running when windows are closed — the tray owns the lifecycle.
  app.on('window-all-closed', () => {});

  app.on('before-quit', () => {
    tracker?.stop();
    store?.dispose();
  });
}
