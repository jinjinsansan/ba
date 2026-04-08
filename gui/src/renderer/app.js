// === Valhalla II -- Renderer (Futuristic BET GUI) ===

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

let isRunning = false;
let logVisible = true;

// --- Title Bar ---
$('#btnMinimize').addEventListener('click', () => window.valhalla.windowMinimize());
$('#btnMaximize').addEventListener('click', () => window.valhalla.windowMaximize());
$('#btnClose').addEventListener('click', () => window.valhalla.windowClose());

// --- License / Setup Screen ---
function showSetup(errorMsg) {
  $('#setupScreen').style.display = 'flex';
  $('#mainContent').style.display = 'none';
  if (errorMsg) {
    $('#setupError').style.display = 'block';
    $('#setupError').textContent = errorMsg;
  }
}

function showMain() {
  $('#setupScreen').style.display = 'none';
  $('#mainContent').style.display = 'block';
}

async function initLicense() {
  const env = await window.valhalla.getEnv();
  const email = env.account_email;

  if (!email) {
    showSetup();
    return;
  }

  // 既存メールでライセンス確認
  const result = await window.valhalla.checkLicense(email);
  if (result.ok) {
    showMain();
  } else {
    showSetup(result.reason);
  }
}

$('#btnActivate').addEventListener('click', async () => {
  const email = $('#setupEmail').value.trim();
  const stakeUser = $('#setupStakeUser').value.trim();
  const stakePass = $('#setupStakePass').value.trim();

  if (!email || !stakeUser || !stakePass) {
    $('#setupError').style.display = 'block';
    $('#setupError').textContent = 'All fields are required.';
    return;
  }

  $('#setupLoading').style.display = 'block';
  $('#btnActivate').disabled = true;
  $('#setupError').style.display = 'none';

  const result = await window.valhalla.checkLicense(email);
  if (!result.ok) {
    $('#setupLoading').style.display = 'none';
    $('#btnActivate').disabled = false;
    $('#setupError').style.display = 'block';
    $('#setupError').textContent = result.reason;
    return;
  }

  await window.valhalla.saveCredentials({ email, stake_username: stakeUser, stake_password: stakePass });
  $('#setupLoading').style.display = 'none';
  showMain();
});

$('#linkBafather').addEventListener('click', () => window.valhalla.openExternal('https://bafather.uk'));

// 起動時にライセンス確認
initLicense();

// --- Auto Updater ---
window.valhalla.onUpdateStatus((data) => {
  const banner = $('#updateBanner');
  const text = $('#updateText');
  const btn = $('#btnInstallUpdate');
  if (data.status === 'available') {
    banner.style.display = 'flex';
    text.textContent = `新バージョン ${data.version} をダウンロード中...`;
    btn.style.display = 'none';
  } else if (data.status === 'downloading') {
    banner.style.display = 'flex';
    text.textContent = `ダウンロード中... ${data.percent}%`;
    btn.style.display = 'none';
  }
});
$('#btnInstallUpdate').addEventListener('click', () => window.valhalla.openUpdatePage());

// --- Start / Stop ---
let sessionTotal = 0;
let _startedAt = 0;  // START押下時刻 (stopped誤検知防止用)

$('#btnStart').addEventListener('click', async () => {
  const config = { ...loadSettings(), table_filter: loadTableFilter() };
  const hasPrev = localStorage.getItem('valhalla_session_state');
  if (hasPrev) {
    const choice = await showContinueDialog();
    if (choice === 'cancel') return;
    config.resume = (choice === 'continue');
  } else {
    config.resume = false;
  }
  if (!config.resume) {
    sessionTotal = 0;
    updateSessionDisplay();
    resetFeed();
  }
  _startedAt = Date.now();
  setRunning(true);
  addLog('Bot starting...', 'info');
  try {
    await window.valhalla.startBot(config);
    addLog('Bot started.', 'info');
  } catch (e) {
    addLog(`Start failed: ${e.message || e}`, 'lose');
    setRunning(false);
  }
});

function updateSessionDisplay() {
  const el = $('#sessionPnl');
  el.textContent = `$${sessionTotal >= 0 ? '+' : ''}${sessionTotal.toFixed(2)}`;
  el.className = 'stat-value ' + (sessionTotal >= 0 ? 'positive' : 'negative');
  persistSessionState();
}

function persistSessionState() {
  try {
    const state = {
      sessionTotal,
      results: results.slice(-200),
      ts: Date.now(),
    };
    localStorage.setItem('valhalla_session_state', JSON.stringify(state));
  } catch {}
}

function restoreSessionState() {
  try {
    const raw = localStorage.getItem('valhalla_session_state');
    if (!raw) return false;
    const state = JSON.parse(raw);
    sessionTotal = state.sessionTotal || 0;
    results.length = 0;
    if (Array.isArray(state.results)) {
      for (const r of state.results) results.push(r);
    }
    updateSessionDisplay();
    renderFeed();
    renderRecent();
    return true;
  } catch { return false; }
}

$('#btnStop').addEventListener('click', async () => {
  await window.valhalla.stopBot();
  setRunning(false);
  addLog('Bot stopped.', 'info');
});

function setRunning(running) {
  isRunning = running;
  $('#btnStart').disabled = running;
  $('#btnStop').disabled = !running;
  $('#btnSkip').disabled = !running;
}

// SKIP TABLE: request agent to exit current table and find new one
$('#btnSkip').addEventListener('click', async () => {
  if (!isRunning) return;
  try {
    await window.valhalla.sendCommand({ type: 'skip_table' });
    addLog('Skip table requested. Searching for new table...', 'info');
  } catch (e) {
    addLog(`Skip failed: ${e.message || e}`, 'lose');
  }
});

// Continue/Reset dialog
function showContinueDialog() {
  return new Promise((resolve) => {
    const modal = $('#continueModal');
    modal.classList.remove('hidden');
    const cleanup = () => {
      modal.classList.add('hidden');
      $('#btnContinue').onclick = null;
      $('#btnResetAll').onclick = null;
      $('#continueClose').onclick = null;
    };
    $('#btnContinue').onclick = () => { restoreSessionState(); cleanup(); resolve('continue'); };
    $('#btnResetAll').onclick = () => {
      localStorage.removeItem('valhalla_session_state');
      sessionTotal = 0;
      updateSessionDisplay();
      resetFeed();
      cleanup();
      resolve('reset');
    };
    $('#continueClose').onclick = () => { cleanup(); resolve('cancel'); };
  });
}

// --- Settings ---
const DEFAULT_SETTINGS = {
  license_key: '',
  chip_base: 1,
  profit_target: 50,
  loss_cut: 200,
  telegram_chat_id: '',
  user_email: '',
  dry_run: false,
};

const SITE_URL = 'https://bafather.uk';
const LAPLACE_API_KEY = 'c6gDoe0xIyBOTQ7bvzRaAHNYn4ZE1W9Mriumqkw8Shf5Jlsd';

async function syncTableFilterToServer(email, filter) {
  if (!email) return;
  try {
    await fetch(`${SITE_URL}/api/bot-config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, bot_config: filter, api_key: LAPLACE_API_KEY }),
    });
  } catch (e) {
    console.warn('[sync] bot-config sync failed:', e);
  }
}

// --- Table Filter ---
const DEFAULT_TABLE_FILTER = {
  players_primary: 10,
  relax_wait_sec: 60,
  min_hands: 20,
  max_hands: 40,
  dragon_limit: 5,
  require_pb: true,
};

function loadTableFilter() {
  try {
    const stored = JSON.parse(localStorage.getItem('valhalla_table_filter') || '{}');
    return { ...DEFAULT_TABLE_FILTER, ...stored };
  } catch { return { ...DEFAULT_TABLE_FILTER }; }
}

function saveTableFilter(f) {
  localStorage.setItem('valhalla_table_filter', JSON.stringify(f));
}

// Stepper state
const _steppers = {};
function initStepper(decId, incId, valId, min, max, step) {
  function clamp(v) { return Math.max(min, Math.min(max, v)); }
  function read() { return parseInt($('#' + valId).textContent) || min; }
  function write(v) { $('#' + valId).textContent = clamp(v); }
  $('#' + decId).addEventListener('click', () => write(read() - step));
  $('#' + incId).addEventListener('click', () => write(read() + step));
  _steppers[valId] = { get: () => parseInt($('#' + valId).textContent) || min, set: write };
}

// Segment state
const _segments = {};
function initSegment(containerId) {
  let cur = null;
  const btns = () => $$('#' + containerId + ' .fx-seg-btn');
  btns().forEach(btn => {
    if (btn.classList.contains('active')) cur = parseInt(btn.dataset.val);
    btn.addEventListener('click', () => {
      btns().forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      cur = parseInt(btn.dataset.val);
    });
  });
  _segments[containerId] = {
    get: () => cur,
    set: (v) => {
      btns().forEach(b => {
        const match = parseInt(b.dataset.val) === v;
        b.classList.toggle('active', match);
        if (match) cur = v;
      });
    }
  };
}

// Toggle state
const _toggles = {};
function initToggle(toggleId, trackId) {
  let on = $('#' + trackId).classList.contains('on');
  $('#' + toggleId).addEventListener('click', () => {
    on = !on;
    $('#' + trackId).classList.toggle('on', on);
  });
  _toggles[trackId] = {
    get: () => on,
    set: (v) => { on = v; $('#' + trackId).classList.toggle('on', v); }
  };
}

// Tab switching
function initModalTabs() {
  function switchTab(active) {
    $$('.modal-tab').forEach(t => t.classList.remove('active'));
    $$('.tab-content').forEach(c => c.classList.add('hidden'));
    if (active === 'bot') {
      $('#tabBotBtn').classList.add('active');
      $('#tabBotContent').classList.remove('hidden');
    } else {
      $('#tabTableBtn').classList.add('active');
      $('#tabTableContent').classList.remove('hidden');
    }
  }
  $('#tabBotBtn').addEventListener('click', () => switchTab('bot'));
  $('#tabTableBtn').addEventListener('click', () => switchTab('table'));
}

function initTableFilterControls() {
  initStepper('ppDec', 'ppInc', 'ppValue', 1, 50, 1);
  initStepper('rwDec', 'rwInc', 'rwValue', 10, 300, 10);
  initStepper('mnDec', 'mnInc', 'mnValue', 5, 40, 5);
  initStepper('mxDec', 'mxInc', 'mxValue', 20, 80, 5);
  initSegment('dragonSeg');
  initToggle('pbToggle', 'pbTrack');

  $('#btnSaveTable').addEventListener('click', () => {
    const f = {
      players_primary: _steppers['ppValue'].get(),
      relax_wait_sec: _steppers['rwValue'].get(),
      min_hands: _steppers['mnValue'].get(),
      max_hands: _steppers['mxValue'].get(),
      dragon_limit: _segments['dragonSeg'].get() ?? DEFAULT_TABLE_FILTER.dragon_limit,
      require_pb: _toggles['pbTrack'].get(),
    };
    saveTableFilter(f);
    syncTableFilterToServer(loadSettings().user_email, f);
    addLog(`Table filter saved: primary≥${f.players_primary}p relax=${f.relax_wait_sec}s hands=${f.min_hands}-${f.max_hands} dragon=${f.dragon_limit||'OFF'} P>B=${f.require_pb}`, 'info');
    $('#settingsModal').classList.add('hidden');
  });

  $('#btnResetTable').addEventListener('click', () => {
    applyTableFilterToUI(DEFAULT_TABLE_FILTER);
    addLog('Table filter reset to defaults.', 'info');
  });
}

function applyTableFilterToUI(f) {
  if (_steppers['ppValue']) _steppers['ppValue'].set(f.players_primary);
  if (_steppers['rwValue']) _steppers['rwValue'].set(f.relax_wait_sec);
  if (_steppers['mnValue']) _steppers['mnValue'].set(f.min_hands);
  if (_steppers['mxValue']) _steppers['mxValue'].set(f.max_hands);
  if (_segments['dragonSeg']) _segments['dragonSeg'].set(f.dragon_limit);
  if (_toggles['pbTrack']) _toggles['pbTrack'].set(f.require_pb);
}

$('#btnSettings').addEventListener('click', () => {
  $('#settingsModal').classList.remove('hidden');
  const s = loadSettings();
  $('#inputLicense').value = s.license_key || '';
  $('#inputChipBase').value = s.chip_base;
  $('#inputProfitTarget').value = s.profit_target;
  $('#inputLossCut').value = s.loss_cut;
  $('#inputTelegramChat').value = s.telegram_chat_id || '';
  $('#inputUserEmail').value = s.user_email || '';
  $('#inputDryRun').checked = !!s.dry_run;
  // Load table filter into UI
  applyTableFilterToUI(loadTableFilter());
  // Reset to BOT tab
  $$('.modal-tab').forEach(t => t.classList.remove('active'));
  $$('.tab-content').forEach(c => c.classList.add('hidden'));
  $('#tabBotBtn').classList.add('active');
  $('#tabBotContent').classList.remove('hidden');
});
$('#settingsClose').addEventListener('click', () => $('#settingsModal').classList.add('hidden'));
$('#btnSaveSettings').addEventListener('click', async () => {
  const settings = {
    license_key: $('#inputLicense').value.trim(),
    chip_base: parseFloat($('#inputChipBase').value) || 1,
    profit_target: parseFloat($('#inputProfitTarget').value) || 50,
    loss_cut: parseFloat($('#inputLossCut').value) || 200,
    telegram_chat_id: $('#inputTelegramChat').value.trim(),
    user_email: $('#inputUserEmail').value.trim(),
    dry_run: $('#inputDryRun').checked,
  };
  localStorage.setItem('valhalla_settings', JSON.stringify(settings));
  $('#settingsModal').classList.add('hidden');
  addLog(`Settings saved. Base:$${settings.chip_base} Target:$${settings.profit_target} LossCut:$${settings.loss_cut}`, 'info');

  // Live-update profit_target & loss_cut if session is running
  if (isRunning) {
    try {
      await window.valhalla.sendCommand({
        type: 'update_config',
        config: {
          profit_target: settings.profit_target,
          loss_cut: settings.loss_cut,
        },
      });
      addLog('Live config update sent (profit target & loss cut).', 'info');
    } catch (e) {
      addLog(`Live update failed: ${e.message || e}`, 'lose');
    }
  }
});

function loadSettings() {
  try {
    const stored = JSON.parse(localStorage.getItem('valhalla_settings') || '{}');
    return { ...DEFAULT_SETTINGS, ...stored };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

// --- Developer Mode ---
const DEV_PASSWORD = 'laplace1749';

function isDevMode() {
  return localStorage.getItem('valhalla_dev_mode') === '1';
}

function setDevMode(on) {
  if (on) localStorage.setItem('valhalla_dev_mode', '1');
  else localStorage.removeItem('valhalla_dev_mode');
  applyDevMode();
}

function applyDevMode() {
  const on = isDevMode();
  const panel = $('#devPanel');
  const status = $('#devModeStatus');
  if (panel) panel.classList.toggle('hidden', !on);
  if (status) status.textContent = `Developer Mode: ${on ? 'ON (click to disable)' : 'OFF'}`;
}

$('#devModeLink').addEventListener('click', () => {
  if (isDevMode()) {
    setDevMode(false);
    addLog('Developer Mode disabled.', 'info');
  } else {
    $('#settingsModal').classList.add('hidden');
    $('#devModeModal').classList.remove('hidden');
    $('#inputDevPassword').value = '';
    $('#inputDevPassword').focus();
  }
});

$('#devModeClose').addEventListener('click', () => {
  $('#devModeModal').classList.add('hidden');
});

$('#btnDevAuth').addEventListener('click', () => {
  const pw = $('#inputDevPassword').value;
  if (pw === DEV_PASSWORD) {
    setDevMode(true);
    $('#devModeModal').classList.add('hidden');
    addLog('Developer Mode UNLOCKED.', 'win');
  } else {
    addLog('Invalid password.', 'lose');
    $('#inputDevPassword').value = '';
    $('#inputDevPassword').focus();
  }
});

$('#inputDevPassword').addEventListener('keypress', (e) => {
  if (e.key === 'Enter') $('#btnDevAuth').click();
});

function updateDevPanel(msg) {
  if (!isDevMode()) return;
  if (typeof msg.current_unit_idx === 'number') $('#devUnitIdx').textContent = msg.current_unit_idx;
  if (typeof msg.current_unit === 'number') $('#devUnit').textContent = `$${msg.current_unit}`;
  if (typeof msg.set_count === 'number') $('#devSet').textContent = `#${msg.set_count + 1}`;
  if (typeof msg.current_turn === 'number') $('#devTurn').textContent = `${msg.current_turn}/7`;
  if (typeof msg.cumulative_profit === 'number') $('#devCumProfit').textContent = `${msg.cumulative_profit >= 0 ? '+' : ''}${msg.cumulative_profit}`;
  if (typeof msg.overshoot === 'number') $('#devOvershoot').textContent = msg.overshoot;
  if (typeof msg.total_bets === 'number') $('#devTotalBets').textContent = msg.total_bets;
}

function renderDevSets(sets) {
  if (!isDevMode()) return;
  const el = $('#devSets');
  if (!el) return;
  if (!sets || sets.length === 0) {
    el.innerHTML = '<div style="color:var(--text-dim); padding:4px 12px;">No completed sets yet</div>';
    return;
  }
  let html = '';
  for (const s of sets) {
    const marks = (s.results || '').split('').map(c =>
      c === 'O' ? '<span class="set-mark-o">O</span>' : '<span class="set-mark-x">X</span>'
    ).join('');
    const sign = s.set_profit >= 0 ? '+' : '';
    const os = (typeof s.overshoot === 'number') ? s.overshoot : '-';
    const slashedCls = s.slashed ? ' slashed' : '';
    const slashMark = s.slashed ? ' <span class="scissors">&#9986;</span>' : '';
    html += `<div class="set-line${slashedCls}"><span class="set-index">#${s.set_index}</span>${marks}<span class="set-meta">${s.wins}W/${s.losses}L ${sign}${s.set_profit} OS:${os}${slashMark}</span></div>`;
  }
  el.innerHTML = html;
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
  const duration = (type === 'profit' || type === 'losscut') ? 2000 : 900;
  setTimeout(() => { el.className = 'flash-overlay'; }, duration);
}

// --- Reset Toast (big banner for profit/loss lock) ---
function showResetToast(title, amount, isProfit) {
  let toast = $('#resetToast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'resetToast';
    toast.className = 'reset-toast';
    document.body.appendChild(toast);
  }
  toast.className = 'reset-toast ' + (isProfit ? 'profit' : 'losscut') + ' show';
  toast.innerHTML = `
    <div class="toast-title">${title}</div>
    <div class="toast-amount">${amount}</div>
    <div class="toast-sub">${isProfit ? 'Locked in. New session.' : 'Stopped loss. New session.'}</div>
  `;
  setTimeout(() => { toast.className = 'reset-toast ' + (isProfit ? 'profit' : 'losscut'); }, 3500);
}

// --- Action Text ---
function setAction(text) {
  $('#actionText').textContent = text;
}

// --- Result Buffer (W/L/T list) ---
// Append-only list of individual hand results.
// - feedRow: shows last 5
// - recentGrid: shows last 20
const MAX_FEED = 10;
const MAX_RECENT = 100;
const results = [];  // 'W' | 'L' | 'T'

function addResult(mark) {
  results.push(mark);
  renderFeed();
  renderRecent();
}

function renderFeed() {
  const row = $('#feedRow');
  const last = results.slice(-MAX_FEED);
  let html = '';
  for (const m of last) {
    const cls = m === 'W' ? 'win' : m === 'L' ? 'lose' : 'tie';
    html += `<span class="feed-dot ${cls}">${m}</span>`;
  }
  html += '<span class="feed-cursor"></span>';
  row.innerHTML = html;
}

function renderRecent() {
  const grid = $('#recentGrid');
  if (results.length === 0) {
    grid.innerHTML = '<div class="shoe-empty">Waiting for results...</div>';
    return;
  }
  const last = results.slice(-MAX_RECENT);
  let html = '';
  for (const m of last) {
    if (m === 'W') html += '<span class="mark-o">O</span>';
    else if (m === 'L') html += '<span class="mark-x">X</span>';
    else html += '<span class="mark-t">T</span>';
  }
  grid.innerHTML = html;
}

function resetFeed() {
  results.length = 0;
  renderFeed();
  renderRecent();
}

// --- Daily P&L tracking (JST timezone, per-round delta aggregation) ---
// Stored as { "YYYY-MM-DD": pnl_amount, ... }
function loadDailyPnl() {
  try { return JSON.parse(localStorage.getItem('valhalla_daily_pnl') || '{}'); }
  catch { return {}; }
}

function saveDailyPnl(data) {
  localStorage.setItem('valhalla_daily_pnl', JSON.stringify(data));
}

function todayKeyJST() {
  // JST = UTC+9
  const now = new Date();
  const utcMs = now.getTime() + (now.getTimezoneOffset() * 60000);
  const jst = new Date(utcMs + 9 * 3600000);
  return `${jst.getFullYear()}-${String(jst.getMonth()+1).padStart(2,'0')}-${String(jst.getDate()).padStart(2,'0')}`;
}

function addRoundToDaily(profitDollars) {
  if (Math.abs(profitDollars) < 0.01) return;
  const data = loadDailyPnl();
  const key = todayKeyJST();
  data[key] = (data[key] || 0) + profitDollars;
  saveDailyPnl(data);
  renderDailyPnl();
}

function renderDailyPnl() {
  const row = $('#dailyRow');
  const data = loadDailyPnl();

  // Today value header
  const today = todayKeyJST();
  const todayVal = data[today] || 0;
  const todayEl = $('#todayPnl');
  if (todayEl) {
    todayEl.textContent = `${todayVal >= 0 ? '+$' : '-$'}${Math.abs(todayVal).toFixed(0)}`;
    todayEl.className = 'today-pnl ' + (todayVal >= 0 ? 'positive' : 'negative');
  }

  const keys = Object.keys(data).sort().slice(-14);
  if (keys.length === 0) {
    row.innerHTML = '<div class="daily-empty">No history yet</div>';
    return;
  }
  let html = '';
  for (const k of keys) {
    const v = data[k];
    const isPos = v >= 0;
    const mmdd = k.slice(5);
    html += `
      <div class="daily-item ${isPos ? 'positive' : 'negative'}">
        <div class="daily-date">${mmdd}</div>
        <div class="daily-pnl ${isPos ? 'positive' : 'negative'}">${isPos ? '+' : ''}$${v.toFixed(0)}</div>
      </div>
    `;
  }
  row.innerHTML = html;
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
        addResult('T');
      } else if (won === true) {
        flashScreen('win');
        addResult('W');
      } else if (won === false) {
        flashScreen('lose');
        addResult('L');
      }

      // Update balance
      if (msg.balance) {
        $('#balance').textContent = `$${msg.balance.toFixed(2)}`;
      }
      // Update session + daily P&L from round_profit delta
      if (typeof msg.round_profit === 'number') {
        sessionTotal += msg.round_profit;
        updateSessionDisplay();
        addRoundToDaily(msg.round_profit);
      }
      break;
    }

    case 'set_complete':
      // In dev mode, show a log line
      if (isDevMode()) {
        const s = msg;
        const sign = s.set_profit >= 0 ? '+' : '';
        addLog(`[DEV] Set #${s.set_index} done: ${s.wins}W/${s.losses}L ${sign}${s.set_profit}ch OS:${s.overshoot}`, 'info');
      }
      break;

    case 'shoe_history':
      // In dev mode, render all sets
      if (isDevMode() && Array.isArray(msg.sets)) {
        renderDevSets(msg.sets);
      }
      break;

    case 'status': {
      $('#betCount').textContent = `${msg.wins || 0}W / ${msg.losses || 0}L`;
      const totalBets = (msg.wins || 0) + (msg.losses || 0);
      if (totalBets > 0) {
        const wr = ((msg.wins || 0) / totalBets * 100).toFixed(1);
        $('#winRate').textContent = `${wr}%`;
      }
      if (msg.balance) {
        $('#balance').textContent = `$${msg.balance.toFixed(2)}`;
      }
      // OS (overshoot) tag in BETS card
      if (typeof msg.overshoot === 'number') {
        const osEl = $('#osValue');
        const os = msg.overshoot;
        osEl.textContent = `OS ${os}`;
        osEl.className = 'os-tag ' + (os === 0 ? '' : os <= 2 ? 'safe' : os <= 4 ? 'warn' : 'danger');
      }
      // Developer panel
      updateDevPanel(msg);
      // Session P&L is tracked client-side from round_profit; don't overwrite here
      break;
    }

    case 'session_reset': {
      const amt = msg.amount || 0;
      const isProfit = msg.is_profit;
      const title = isProfit ? 'PROFIT TARGET HIT' : 'LOSS CUT';
      const sign = amt >= 0 ? '+' : '-';
      showResetToast(title, `${sign}$${Math.abs(amt).toFixed(0)}`, isProfit);
      flashScreen(isProfit ? 'profit' : 'losscut');
      addLog(`=== ${title} ===  ${sign}$${Math.abs(amt).toFixed(0)}`, isProfit ? 'win' : 'lose');
      // Reset session total (daily total stays)
      sessionTotal = 0;
      updateSessionDisplay();
      break;
    }

    case 'error':
      addLog(`Error: ${msg.message}`, 'lose');
      break;

    case 'stopped':
      // START直後(3秒以内)の stopped は旧プロセスの遅延シグナル→無視
      if (_startedAt && Date.now() - _startedAt < 3000) {
        console.log('[UI] Ignoring stale stopped signal from old process');
        break;
      }
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
// ONE-TIME full reset requested by user
localStorage.removeItem('valhalla_daily_pnl');
localStorage.removeItem('valhalla_session_state');
sessionTotal = 0;
results.length = 0;
setRunning(false);
updateSessionDisplay();
setAction('Ready. Press START to begin.');
addLog('LAPLACE ready. All data cleared.', 'info');
renderDailyPnl();
renderFeed();
renderRecent();
applyDevMode();
initModalTabs();
initTableFilterControls();
applyTableFilterToUI(loadTableFilter());
