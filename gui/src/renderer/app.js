// === Valhalla II -- Renderer (Futuristic BET GUI) ===

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
}

// --- Settings ---
$('#btnSettings').addEventListener('click', () => {
  $('#settingsModal').classList.remove('hidden');
  const s = loadSettings();
  $('#inputLicense').value = s.license_key || '';
  $('#inputChipBase').value = s.chip_base || 1;
  $('#inputLossCut').value = s.loss_cut || 200;
  $('#inputTelegramChat').value = s.telegram_chat_id || '';
  $('#inputDryRun').checked = s.dry_run || false;
});
$('#settingsClose').addEventListener('click', () => $('#settingsModal').classList.add('hidden'));
$('#btnSaveSettings').addEventListener('click', () => {
  const settings = {
    license_key: $('#inputLicense').value.trim(),
    chip_base: parseFloat($('#inputChipBase').value) || 1,
    loss_cut: parseInt($('#inputLossCut').value) || 200,
    telegram_chat_id: $('#inputTelegramChat').value.trim(),
    dry_run: $('#inputDryRun').checked,
  };
  localStorage.setItem('valhalla_settings', JSON.stringify(settings));
  $('#settingsModal').classList.add('hidden');
  addLog('Settings saved.', 'info');
});

function loadSettings() {
  try { return JSON.parse(localStorage.getItem('valhalla_settings') || '{}'); }
  catch { return {}; }
}

// --- Log ---
$('#logToggle').addEventListener('click', () => {
  logVisible = !logVisible;
  $('#logPanel').classList.toggle('hidden', !logVisible);
  $('#logToggle').innerHTML = logVisible ? 'CONSOLE &#x25B2;' : 'CONSOLE &#x25BC;';
});

function addLog(text, type = '') {
  const el = $('#logContent');
  const t = new Date().toLocaleTimeString();
  const cls = type ? ` class="log-${type}"` : '';
  el.innerHTML += `<span${cls}>[${t}] ${esc(text)}</span>\n`;
  el.scrollTop = el.scrollHeight;
}

function esc(text) {
  const d = document.createElement('div');
  d.textContent = text;
  return d.innerHTML;
}

// --- Flash Effect ---
function flashScreen(type) {
  const el = $('#flashOverlay');
  el.className = 'flash-overlay ' + type;
  setTimeout(() => { el.className = 'flash-overlay'; }, 900);
}

// --- Action Text ---
function setAction(text) {
  $('#actionText').textContent = text;
}

// --- Live Feed ---
let lastFeedLen = 0;

function updateFeed(turnsDisplay) {
  const row = $('#feedRow');
  const newLen = turnsDisplay.length;

  // Only add new dots (avoid re-rendering all)
  if (newLen > lastFeedLen) {
    for (let i = lastFeedLen; i < newLen; i++) {
      const ch = turnsDisplay[i];
      const dot = document.createElement('span');
      dot.className = 'feed-dot ' + (ch === 'O' ? 'win' : 'lose');
      dot.textContent = ch === 'O' ? 'W' : 'L';
      // Insert before cursor
      const cursor = row.querySelector('.feed-cursor');
      row.insertBefore(dot, cursor);
    }
    lastFeedLen = newLen;
  } else if (newLen < lastFeedLen) {
    // Set was reset — clear feed
    resetFeed();
  }
}

function addTieDot() {
  const row = $('#feedRow');
  const dot = document.createElement('span');
  dot.className = 'feed-dot tie';
  dot.textContent = 'T';
  const cursor = row.querySelector('.feed-cursor');
  row.insertBefore(dot, cursor);
}

function resetFeed() {
  const row = $('#feedRow');
  row.innerHTML = '<span class="feed-cursor"></span>';
  lastFeedLen = 0;
}

// --- Shoe History ---
function updateShoeHistory(sets) {
  const grid = $('#shoeGrid');
  if (!sets || sets.length === 0) {
    grid.innerHTML = '<div class="shoe-empty">No sets completed yet</div>';
    return;
  }
  grid.innerHTML = '';
  for (const s of sets) {
    const row = document.createElement('div');
    const isPos = s.set_profit >= 0;
    row.className = 'shoe-row ' + (isPos ? 'positive' : 'negative');

    const marks = s.results.split('').map(ch => {
      if (ch === 'O') return '<span class="mark-o">O</span>';
      if (ch === 'X') return '<span class="mark-x">X</span>';
      return ch;
    }).join('');

    row.innerHTML = `
      <span class="shoe-num">#${s.set_index}</span>
      <span class="shoe-marks">${marks}</span>
      <span class="shoe-pnl ${isPos ? 'positive' : 'negative'}">${s.set_profit >= 0 ? '+' : ''}${s.set_profit}</span>
    `;
    grid.appendChild(row);
  }
  grid.scrollTop = grid.scrollHeight;
}

// --- Agent Messages ---
window.valhalla.onAgentMessage((msg) => {
  switch (msg.type) {
    case 'action':
      setAction(msg.message || '');
      break;

    case 'round_result': {
      const r = msg.result;
      const won = msg.won;
      if (r === 'tie') {
        setAction('Tie -- BET returned');
        addTieDot();
      } else if (won === true) {
        flashScreen('win');
      } else if (won === false) {
        flashScreen('lose');
      }
      updateFeed(msg.turns_display || '');

      // Update balance
      if (msg.balance) {
        $('#balance').textContent = `$${msg.balance.toFixed(2)}`;
      }
      // Update P&L
      const cm = msg.cumulative_money || 0;
      const pnlEl = $('#sessionPnl');
      pnlEl.textContent = `$${cm >= 0 ? '+' : ''}${cm.toFixed(2)}`;
      pnlEl.className = 'stat-value ' + (cm >= 0 ? 'positive' : 'negative');
      break;
    }

    case 'set_complete':
      addLog(`Set #${msg.set_index}: ${msg.wins}W/${msg.losses}L P&L:${msg.set_profit >= 0 ? '+' : ''}${msg.set_profit}`,
        msg.set_profit >= 0 ? 'win' : 'lose');
      setTimeout(resetFeed, 1500);
      break;

    case 'shoe_history':
      updateShoeHistory(msg.sets || []);
      break;

    case 'status':
      updateFeed(msg.turns_display || '');
      $('#betCount').textContent = `${msg.wins || 0}W / ${msg.losses || 0}L`;
      $('#unitInfo').textContent = `${msg.current_unit || 1}x`;
      if (msg.balance) {
        $('#balance').textContent = `$${msg.balance.toFixed(2)}`;
      }
      const pnl = msg.cumulative_money || 0;
      const pe = $('#sessionPnl');
      pe.textContent = `$${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}`;
      pe.className = 'stat-value ' + (pnl >= 0 ? 'positive' : 'negative');
      break;

    case 'session_reset':
      addLog(`Session reset: ${msg.reason}`, msg.reason === 'profit_stop' ? 'win' : 'lose');
      resetDots();
      break;

    case 'error':
      addLog(`Error: ${msg.message}`, 'lose');
      break;

    case 'stopped':
      setRunning(false);
      setAction('Stopped');
      addLog('Bot stopped.');
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
  text.trim().split('\n').forEach(line => { if (line.trim()) addLog(line); });
});

// --- Init ---
setRunning(false);
setAction('Ready. Press START to begin.');
addLog('Valhalla II ready.', 'info');
