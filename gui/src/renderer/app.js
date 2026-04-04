// === Valhalla II -- Renderer (Control Panel Only) ===

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

let isRunning = false;
let logVisible = false;

// --- Title Bar ---
$('#btnMinimize').addEventListener('click', () => window.valhalla.windowMinimize());
$('#btnMaximize').addEventListener('click', () => window.valhalla.windowMaximize());
$('#btnClose').addEventListener('click', () => window.valhalla.windowClose());

// --- Start / Stop ---
$('#btnStart').addEventListener('click', async () => {
  const config = loadSettings();
  await window.valhalla.startBot(config);
  setRunning(true);
  addLog('Bot started.', 'info');
});

$('#btnStop').addEventListener('click', async () => {
  await window.valhalla.stopBot();
  setRunning(false);
  addLog('Bot stopped.', 'info');
});

function setRunning(running) {
  isRunning = running;
  $('#btnStart').disabled = running;
  $('#btnStop').disabled = !running;
  $('#statusDot').className = 'status-indicator' + (running ? ' running' : '');
  $('#statusText').textContent = running ? 'Running' : 'Idle';
}

// --- Settings ---
$('#btnSettings').addEventListener('click', () => {
  $('#settingsModal').classList.remove('hidden');
  const settings = loadSettings();
  $('#inputLicense').value = settings.license_key || '';
  $('#inputChipBase').value = settings.chip_base || 1;
  $('#inputLossCut').value = settings.loss_cut || 200;
  $('#inputTelegramChat').value = settings.telegram_chat_id || '';
});

$('#settingsClose').addEventListener('click', () => {
  $('#settingsModal').classList.add('hidden');
});

$('#btnSaveSettings').addEventListener('click', () => {
  const settings = {
    license_key: $('#inputLicense').value.trim(),
    chip_base: parseFloat($('#inputChipBase').value) || 1,
    loss_cut: parseInt($('#inputLossCut').value) || 200,
    telegram_chat_id: $('#inputTelegramChat').value.trim(),
  };
  localStorage.setItem('valhalla_settings', JSON.stringify(settings));
  $('#settingsModal').classList.add('hidden');
  addLog('Settings saved.', 'info');
});

function loadSettings() {
  try {
    return JSON.parse(localStorage.getItem('valhalla_settings') || '{}');
  } catch {
    return {};
  }
}

// --- Log Panel ---
$('#logToggle').addEventListener('click', () => {
  logVisible = !logVisible;
  $('#logPanel').classList.toggle('hidden', !logVisible);
  $('#logToggle').innerHTML = logVisible ? 'Hide Log &#x25B2;' : 'Show Log &#x25BC;';
});

function addLog(text, type = '') {
  const el = $('#logContent');
  const time = new Date().toLocaleTimeString();
  const cls = type ? ` class="log-${type}"` : '';
  el.innerHTML += `<span${cls}>[${time}] ${escapeHtml(text)}</span>\n`;
  el.scrollTop = el.scrollHeight;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// --- Agent Messages ---
window.valhalla.onAgentMessage((msg) => {
  switch (msg.type) {
    case 'status':
      updateStatus(msg);
      break;
    case 'turn_result':
      updateTurnResult(msg);
      addLog(`Turn ${msg.turn_index + 1}/7: ${msg.result.toUpperCase()} -- ${msg.won ? 'Won!' : 'Lost'}`,
        msg.won ? 'win' : 'lose');
      break;
    case 'set_complete':
      addLog(`Set #${msg.set_index} complete: ${msg.wins}W/${msg.losses}L, P&L: ${msg.profit}`,
        msg.profit >= 0 ? 'win' : 'lose');
      break;
    case 'session_reset':
      addLog(`Session reset: ${msg.reason} (${msg.profit} chips)`,
        msg.reason === 'profit_stop' ? 'win' : 'lose');
      break;
    case 'browser_status':
      updateBrowserStatus(msg.state);
      break;
    case 'error':
      addLog(`Error: ${msg.message}`, 'lose');
      break;
    case 'stopped':
      setRunning(false);
      addLog(`Bot stopped (exit code: ${msg.code}).`);
      break;
    case 'log':
      addLog(msg.message || '');
      break;
    default:
      if (msg.message) addLog(msg.message);
      break;
  }
});

window.valhalla.onAgentLog((text) => {
  const lines = text.trim().split('\n');
  for (const line of lines) {
    if (line.trim()) addLog(line);
  }
});

// --- Status Update ---
function updateStatus(msg) {
  const pnl = msg.cumulative_money || 0;
  const pnlEl = $('#sessionPnl');
  pnlEl.textContent = `$${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}`;
  pnlEl.className = 'stat-value ' + (pnl >= 0 ? 'positive' : 'negative');

  $('#betCount').textContent = `${msg.wins || 0}W / ${msg.losses || 0}L`;
  $('#roundInfo').textContent = `Set #${msg.set_count || 0} | Turn ${msg.current_turn || 0}/7 | Unit: ${msg.current_unit || 1}`;
}

function updateBrowserStatus(state) {
  const dot = $('#browserDot');
  const text = $('#browserText');
  const states = {
    'launching': { cls: 'warning', txt: 'Launching browser...' },
    'login_required': { cls: 'warning', txt: 'Login required (check browser)' },
    'logged_in': { cls: 'info', txt: 'Logged in' },
    'lobby_ready': { cls: 'info', txt: 'Baccarat lobby loaded' },
    'ws_connected': { cls: 'success', txt: 'Evolution WS connected' },
  };
  const s = states[state] || { cls: '', txt: state };
  dot.className = 'browser-dot ' + s.cls;
  text.textContent = s.txt;
}

function updateTurnResult(msg) {
  const dots = $$('.turn-dot');
  const turnIdx = msg.turn_index;
  if (turnIdx >= 0 && turnIdx < 7) {
    const dot = dots[turnIdx];
    dot.className = 'turn-dot ' + (msg.won ? 'win' : 'lose');
    dot.textContent = msg.won ? 'W' : 'L';
  }

  if (turnIdx + 1 < 7) {
    dots[turnIdx + 1].className = 'turn-dot current';
  }

  if (turnIdx === 6) {
    setTimeout(() => {
      dots.forEach(d => {
        d.className = 'turn-dot empty';
        d.textContent = '';
      });
      if (isRunning) dots[0].className = 'turn-dot current';
    }, 3000);
  }

  const resultText = msg.won ? 'Won!' : 'Lost';
  $('#turnLabel').textContent = `Turn ${turnIdx + 1}/7: ${resultText}`;
}

// --- Init ---
setRunning(false);
addLog('Valhalla II ready.', 'info');
