const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('iris', {
  getState: () => ipcRenderer.invoke('get-state'),
  getReport: () => ipcRenderer.invoke('get-report'),
  toggleTracking: () => ipcRenderer.invoke('toggle-tracking'),
  toggleEyeCare: () => ipcRenderer.invoke('toggle-eyecare'),
  openReport: () => ipcRenderer.invoke('open-report'),
  hideWidget: () => ipcRenderer.invoke('hide-widget'),
  onState: (fn) => ipcRenderer.on('state', (_e, s) => fn(s)),
  onEyeBreak: (fn) => ipcRenderer.on('eye-break', () => fn()),
});
