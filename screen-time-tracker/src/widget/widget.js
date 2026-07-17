const $ = (id) => document.getElementById(id);

let state = null;

function fmt(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function fmtCountdown(ms) {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

function render() {
  if (!state) return;
  $('totalTime').textContent = fmt(state.today.totalSeconds);
  $('currentApp').textContent = state.enabled ? (state.currentApp || 'idle / unknown') : 'paused';
  $('topApp').textContent = state.today.topApp
    ? `${state.today.topApp.name} · ${fmt(state.today.topApp.seconds)}` : '—';

  $('trackToggle').className = `toggle ${state.enabled ? 'on' : 'off'}`;
  $('trackLabel').textContent = state.enabled ? 'Tracking' : 'Paused';
  $('eyeToggle').className = `toggle ${state.eyeCareOn ? 'on' : 'off'}`;
  $('eyeState').textContent = state.eyeCareOn ? '' : '(off)';
}

function tickCountdown() {
  if (state && state.eyeCareOn) {
    $('breakIn').textContent = fmtCountdown(state.nextBreakAt - Date.now());
  } else {
    $('breakIn').textContent = '--:--';
  }
}

async function init() {
  if (!window.iris) return; // opened outside Electron
  state = await window.iris.getState();
  render();

  window.iris.onState((s) => { state = s; render(); });
  window.iris.onEyeBreak(() => {
    $('breakflash').classList.add('show');
    setTimeout(() => $('breakflash').classList.remove('show'), 20000);
  });

  $('trackToggle').onclick = async () => { state = await window.iris.toggleTracking(); render(); };
  $('eyeToggle').onclick = async () => { state = await window.iris.toggleEyeCare(); render(); };
  $('reportBtn').onclick = () => window.iris.openReport();
  $('hideBtn').onclick = () => window.iris.hideWidget();

  setInterval(tickCountdown, 1000);
}

init();
