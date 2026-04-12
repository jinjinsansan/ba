// === Valhalla II -- Renderer (Futuristic BET GUI) ===

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

let isRunning = false;
let logVisible = true;
let guiVariant = 'dev';

const I18N = {
  dev: {
    update_open: 'ダウンロードページを開く',
    update_available: '新バージョン {version} をダウンロード中...',
    update_downloading: 'ダウンロード中... {percent}%',
    setup_subtitle: 'ライセンス認証',
    setup_account_email: 'bafather.uk アカウントメール',
    setup_stake_email: 'Stake.com メール',
    setup_stake_pass: 'Stake.com パスワード',
    setup_email_placeholder: 'example@email.com',
    setup_stake_email_placeholder: 'stake@email.com',
    setup_activate: '認証する',
    setup_verifying: 'ライセンス確認中...',
    setup_no_account: 'アカウントがない場合は',
    setup_required: '全て入力してください。',
    action_initializing: '初期化中...',
    stat_balance: '残高',
    stat_session: 'セッション損益',
    stat_bets: 'BET数',
    stat_winrate: '勝率',
    laplace_panel_title: 'ラプラスパネル',
    laplace_panel_badge: '開発',
    laplace_unit_idx: '現在ユニットIdx',
    laplace_unit: '現在ユニット($)',
    laplace_set: '現在セット',
    laplace_turn: 'セット内ターン',
    laplace_set_profit: 'セット損益',
    laplace_cum_profit: '累計損益',
    laplace_overshoot: 'オーバーシュート',
    laplace_total_bets: '総BET数',
    laplace_set_history: 'セット履歴 (7ハンド)',
    daily_total: 'デイリー損益',
    live_feed: 'ライブフィード',
    recent_hands: '直近ハンド',
    btn_start: '開始',
    btn_stop: '停止',
    btn_skip: '次テーブル',
    btn_settings: '設定',
    continue_title: '前回セッション検出',
    continue_desc: '前回のセッションが見つかりました。開始方法を選択してください。',
    continue_btn: '続きから再開',
    reset_btn: 'リセット (デイリー維持)',
    log_toggle: 'ログ ▲',
    settings_title: '設定',
    settings_base_bet: '基本BET ($)',
    settings_profit_target: '利確目標 ($)',
    settings_loss_cut: '損切り ($)',
    settings_telegram: 'Telegram チャットID',
    settings_telegram_placeholder: '任意',
    settings_account_email: 'アカウントメール',
    settings_email_placeholder: 'your@email.com',
    settings_dry_run: 'テストモード (実BETなし)',
    settings_bet_mode: 'BETモード',
    settings_save: '保存',
    mode_1drop: '1-ドロップ (観察→入室)',
    mode_normal: '通常 (同一テーブル)',
    mode_mix: 'ミックス (OS≥20で1-ドロップ)',
    mode_sync: '同期 (上位テーブル監視)',
    mode_sync_pause: '同期+停止 (BBで停止/P再開)',
    mode_pattern: 'パターン (Strategy A)',
    mode_pattern_test: 'パターンテスト ($1固定)',
    mode_counter: 'カウンター (逆張り)',
    mode_counter_flat: 'カウンターFlat ($1固定)',
    log_bot_starting: 'ボット起動中...',
    log_bot_started: 'ボット起動完了。',
    log_start_failed: '起動失敗: {error}',
    log_bot_stopped: '停止しました。',
    log_skip_requested: 'テーブル移動を要求しました。',
    log_skip_failed: '移動失敗: {error}',
    log_settings_saved: '設定保存: 基本${base} 目標${profit} 損切り${loss}',
    log_live_update_sent: 'ライブ更新送信 (利確/損切 + モード: {mode})',
    log_live_update_failed: 'ライブ更新失敗: {error}',
    action_ready: '準備完了。STARTで開始',
    log_ready: 'LAPLACE準備完了。初期化済み。',
    log_pnl_synced: 'VPSからセッションPNLを同期: ${amount}',
    toast_profit: '利確確定。新セッション開始。',
    toast_loss: '損切り確定。新セッション開始。',
    reset_profit: '利確達成',
    reset_loss: '損切り',
  },
};

function t(key, fallback = '') {
  const map = I18N[guiVariant] || {};
  return map[key] || fallback || key;
}

function format(template, values) {
  if (!template) return '';
  return Object.entries(values || {}).reduce(
    (acc, [k, v]) => acc.replace(new RegExp(`\\{${k}\\}`, 'g'), v),
    template
  );
}

function applyTranslations() {
  document.querySelectorAll('[data-i18n]').forEach((el) => {
    const key = el.dataset.i18n;
    const value = (I18N[guiVariant] || {})[key];
    if (value) el.textContent = value;
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
    const key = el.dataset.i18nPlaceholder;
    const value = (I18N[guiVariant] || {})[key];
    if (value) el.setAttribute('placeholder', value);
  });
  const header = $('#devSetsHeader');
  if (header) {
    if (guiVariant === 'dev') {
      header.innerHTML = '<span>セット</span><span>結果</span><span>勝敗/損益</span>';
    } else {
      header.innerHTML = '<span>SET</span><span>RESULTS</span><span>W/L & P/L</span>';
    }
  }
  const logToggle = $('#logToggle');
  if (logToggle) {
    logToggle.innerHTML = getLogToggleText(logVisible);
  }
}

function applyVariant() {
  document.documentElement.dataset.variant = guiVariant;
  if (guiVariant === 'dev') {
    localStorage.setItem('valhalla_dev_mode', '1');
  }
  if (guiVariant === 'user') {
    document.querySelectorAll('.dev-only').forEach(el => el.remove());
  }
  applyDevMode();
}

function getLogToggleText(open) {
  const label = guiVariant === 'dev' ? 'ログ' : 'CONSOLE';
  return `${label} ${open ? '&#x25B2;' : '&#x25BC;'}`;
}

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
  guiVariant = (env.gui_variant || 'dev').toLowerCase();
  document.documentElement.lang = guiVariant === 'dev' ? 'ja' : 'en';
  applyVariant();
  applyTranslations();
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
    $('#setupError').textContent = t('setup_required', 'All fields are required.');
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
    text.textContent = format(
      t('update_available', `Downloading new version ${data.version}...`),
      { version: data.version }
    );
    btn.style.display = 'none';
  } else if (data.status === 'downloading') {
    banner.style.display = 'flex';
    text.textContent = format(
      t('update_downloading', `Downloading... ${data.percent}%`),
      { percent: data.percent }
    );
    btn.style.display = 'none';
  }
});
$('#btnInstallUpdate').addEventListener('click', () => window.valhalla.openUpdatePage());

// --- Start / Stop ---
let sessionTotal = 0;
let _startedAt = 0;  // START押下時刻 (stopped誤検知防止用)
let _pnlSynced = false;  // VPS累計PNL同期フラグ（resume時に1回だけ同期）
let _lastCumulativeMoney = 0;  // 前回の cumulative_money (daily 差分計算用)

$('#btnStart').addEventListener('click', async () => {
  // Syncモード用: 起動時にサーバーから最新の推奨テーブルを取得
  await fetchRecommendedTables();
  const config = {
    ...loadSettings(),
    site_api_key: LAPLACE_API_KEY,
    resume_results: (typeof results !== 'undefined' && Array.isArray(results)) ? results.slice() : [],
    table_filter: loadTableFilter(),
    recommended_tables: getEnabledRecommendedTables(),
  };
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
    _lastCumulativeMoney = 0;  // 新規開始 → リセット
    _pnlSynced = true;  // 新規開始 → 同期不要
    updateSessionDisplay();
    resetFeed();
  } else {
    _pnlSynced = false;  // resume → 最初のstatusでVPS累計を同期
    // Supabaseからgui_stateを復元
    await restoreGuiStateFromServer();
    // resume時は復元された sessionTotal を _lastCumulativeMoney と同期
    _lastCumulativeMoney = sessionTotal;
  }
  config.resume_results = Array.isArray(results) ? results.slice() : [];
  _startedAt = Date.now();
  setRunning(true);
  addLog(t('log_bot_starting', 'Bot starting...'), 'info');
  try {
    await window.valhalla.startBot(config);
    addLog(t('log_bot_started', 'Bot started.'), 'info');
  } catch (e) {
    addLog(format(t('log_start_failed', 'Start failed: {error}'), { error: e.message || e }), 'lose');
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
    _lastCumulativeMoney = sessionTotal;  // Phase A1+: 復元時も同期
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
  addLog(t('log_bot_stopped', 'Bot stopped.'), 'info');
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
    addLog(t('log_skip_requested', 'Skip table requested. Searching for new table...'), 'info');
  } catch (e) {
    addLog(format(t('log_skip_failed', 'Skip failed: {error}'), { error: e.message || e }), 'lose');
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
      _lastCumulativeMoney = 0;  // Phase A1+: 同期
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
  bet_mode: '1drop',
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

// --- Recommended Tables (Supabase) ---
async function fetchRecommendedTables() {
  const email = loadSettings().user_email;
  const qs = email
    ? `?email=${encodeURIComponent(email)}&api_key=${encodeURIComponent(LAPLACE_API_KEY)}`
    : `?api_key=${encodeURIComponent(LAPLACE_API_KEY)}`;
  try {
    const res = await fetch(`${SITE_URL}/api/recommended-tables${qs}`);
    const data = await res.json();
    if (data.tables && Array.isArray(data.tables)) {
      localStorage.setItem('recommended_tables', JSON.stringify(data.tables));
      localStorage.setItem('recommended_tables_source', data.source || 'unknown');
      return data.tables;
    }
  } catch (e) {
    console.warn('[sync] recommended-tables fetch failed:', e);
  }
  // fallback
  const cached = localStorage.getItem('recommended_tables');
  return cached ? JSON.parse(cached) : [
    { name: 'Japanese Speed Baccarat A', enabled: true, priority: 1 },
    { name: 'Korean Speed Baccarat B', enabled: true, priority: 2 },
  ];
}

async function saveRecommendedTablesToServer(tables) {
  const email = loadSettings().user_email;
  if (!email) return;
  try {
    await fetch(`${SITE_URL}/api/recommended-tables`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, api_key: LAPLACE_API_KEY, tables }),
    });
  } catch (e) {
    console.warn('[sync] recommended-tables save failed:', e);
  }
}

function getEnabledRecommendedTables() {
  const cached = localStorage.getItem('recommended_tables');
  if (!cached) return ['Japanese Speed Baccarat A', 'Korean Speed Baccarat B'];
  try {
    const tables = JSON.parse(cached);
    return tables
      .filter(t => t.enabled !== false)
      .sort((a, b) => (a.priority || 999) - (b.priority || 999))
      .map(t => t.name);
  } catch {
    return ['Japanese Speed Baccarat A', 'Korean Speed Baccarat B'];
  }
}

// --- GUI State Persistence (Supabase) ---
let _guiSyncTimer = null;
let _guiSyncPending = false;

function _getGuiState() {
  return {
    session_total: sessionTotal,
    daily_pnl: loadDailyPnl(),
    results: results.slice(-200),
    bet_mode: (loadSettings().bet_mode || '1drop'),
    updated_at: new Date().toISOString(),
  };
}

async function syncGuiStateToServer() {
  const email = loadSettings().user_email;
  if (!email) return;
  try {
    await fetch(`${SITE_URL}/api/gui-state`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, api_key: LAPLACE_API_KEY, gui_state: _getGuiState() }),
    });
  } catch (e) {
    console.warn('[sync] gui-state sync failed:', e);
  }
}

function scheduleGuiStateSync() {
  _guiSyncPending = true;
  if (_guiSyncTimer) return; // already scheduled
  _guiSyncTimer = setTimeout(() => {
    _guiSyncTimer = null;
    if (_guiSyncPending) {
      _guiSyncPending = false;
      syncGuiStateToServer();
    }
  }, 5000); // debounce 5s
}

async function loadGuiStateFromServer() {
  const email = loadSettings().user_email;
  if (!email) return null;
  try {
    const res = await fetch(`${SITE_URL}/api/gui-state?email=${encodeURIComponent(email)}&api_key=${encodeURIComponent(LAPLACE_API_KEY)}`);
    const data = await res.json();
    return data.gui_state || null;
  } catch (e) {
    console.warn('[sync] gui-state load failed:', e);
    return null;
  }
}

async function restoreGuiStateFromServer() {
  const state = await loadGuiStateFromServer();
  if (!state) return false;
  if (typeof state.session_total === 'number') {
    sessionTotal = state.session_total;
    _lastCumulativeMoney = state.session_total;  // Phase A1+: 復元時も同期
    updateSessionDisplay();
  }
  if (state.daily_pnl && typeof state.daily_pnl === 'object') {
    saveDailyPnl(state.daily_pnl);
    renderDailyPnl();
  }
  if (Array.isArray(state.results) && state.results.length > 0) {
    results.length = 0;
    for (const r of state.results) results.push(r);
    renderFeed();
    renderRecent();
  }
  addLog('GUI state restored from server.', 'info');
  return true;
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
  const botBtn = $('#tabBotBtn');
  const tableBtn = $('#tabTableBtn');
  if (!botBtn || !tableBtn) return;
  function switchTab(active) {
    $$('.modal-tab').forEach(t => t.classList.remove('active'));
    $$('.tab-content').forEach(c => c.classList.add('hidden'));
    if (active === 'bot') {
      botBtn.classList.add('active');
      $('#tabBotContent').classList.remove('hidden');
    } else {
      tableBtn.classList.add('active');
      $('#tabTableContent').classList.remove('hidden');
    }
  }
  botBtn.addEventListener('click', () => switchTab('bot'));
  tableBtn.addEventListener('click', () => switchTab('table'));
}

function initTableFilterControls() {
  if (!$('#btnSaveTable')) return;
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
  const chipBaseEl = $('#inputChipBase');
  if (chipBaseEl) chipBaseEl.value = s.chip_base;
  const ptEl = $('#inputProfitTarget');
  if (ptEl) ptEl.value = s.profit_target;
  const lcEl = $('#inputLossCut');
  if (lcEl) lcEl.value = s.loss_cut;
  const tgEl = $('#inputTelegramChat');
  if (tgEl) tgEl.value = s.telegram_chat_id || '';
  const mailEl = $('#inputUserEmail');
  if (mailEl) mailEl.value = s.user_email || '';
  const dryEl = $('#inputDryRun');
  if (dryEl) dryEl.checked = !!s.dry_run;
  const modeEl = $('#inputBetMode');
  if (modeEl) modeEl.value = s.bet_mode || '1drop';
  const tabContent = $('#tabBotContent');
  if (tabContent) tabContent.classList.remove('hidden');
});
$('#settingsClose').addEventListener('click', () => $('#settingsModal').classList.add('hidden'));
$('#btnSaveSettings').addEventListener('click', async () => {
  const licenseInput = $('#inputLicense');
  const settings = {
    license_key: licenseInput ? licenseInput.value.trim() : '',
    chip_base: parseFloat($('#inputChipBase').value) || 1,
    profit_target: parseFloat($('#inputProfitTarget').value) || 50,
    loss_cut: parseFloat($('#inputLossCut').value) || 200,
    telegram_chat_id: $('#inputTelegramChat').value.trim(),
    user_email: $('#inputUserEmail').value.trim(),
    dry_run: $('#inputDryRun').checked,
    bet_mode: $('#inputBetMode').value || '1drop',
  };
  localStorage.setItem('valhalla_settings', JSON.stringify(settings));
  $('#settingsModal').classList.add('hidden');
  addLog(
    format(
      t('log_settings_saved', 'Settings saved. Base:${base} Target:${profit} LossCut:${loss}'),
      { base: settings.chip_base, profit: settings.profit_target, loss: settings.loss_cut }
    ),
    'info'
  );

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
      // Live BET mode switch
      await window.valhalla.sendCommand({
        type: 'change_mode',
        mode: settings.bet_mode,
      });
      addLog(format(t('log_live_update_sent', 'Live config update sent (profit/loss + mode: {mode}).'), { mode: settings.bet_mode }), 'info');
    } catch (e) {
      addLog(format(t('log_live_update_failed', 'Live update failed: {error}'), { error: e.message || e }), 'lose');
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
function isDevMode() {
  return guiVariant === 'dev';
}

function applyDevMode() {
  const panel = $('#devPanel');
  if (panel) panel.classList.toggle('hidden', !isDevMode());
}

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
    el.innerHTML = `<div style="color:var(--text-dim); padding:4px 12px;">${guiVariant === 'dev' ? 'まだセットがありません' : 'No completed sets yet'}</div>`;
    return;
  }
  let html = '';
  for (const s of sets) {
    const marks = (s.results || '').split('').map(c => {
      if (c === 'O') return `<span class="set-mark-o">${guiVariant === 'dev' ? '〇' : 'O'}</span>`;
      return `<span class="set-mark-x">${guiVariant === 'dev' ? '✕' : 'X'}</span>`;
    }).join('');
    const sign = s.set_profit >= 0 ? '+' : '';
    const os = (typeof s.overshoot === 'number') ? s.overshoot : '-';
    const slashedCls = s.slashed ? ' slashed' : '';
    const slashMark = s.slashed ? ' <span class="scissors">&#9986;</span>' : '';
    const wl = guiVariant === 'dev'
      ? `${s.wins}勝/${s.losses}敗`
      : `${s.wins}W/${s.losses}L`;
    html += `<div class="set-line${slashedCls}"><span class="set-index">#${s.set_index}</span><span class="set-marks">${marks}</span><span class="set-meta">${wl} ${sign}${s.set_profit} OS:${os}${slashMark}</span></div>`;
  }
  el.innerHTML = html;
}

// --- Log ---
$('#logToggle').addEventListener('click', () => {
  logVisible = !logVisible;
  $('#logPanel').classList.toggle('hidden', !logVisible);
  $('#logToggle').innerHTML = getLogToggleText(logVisible);
});

function addLog(text, type = '') {
  const el = $('#logContent');
  if (!text || shouldIgnoreLog(text)) return;
  const t = new Date().toLocaleTimeString();
  const cls = type ? ` class="log-${type}"` : '';
  el.innerHTML += `<span${cls}>[${t}] ${esc(text)}</span>\n`;
  el.scrollTop = el.scrollHeight;
}

function shouldIgnoreLog(text) {
  const line = text.trim();
  if (!line) return true;
  if (line.includes('[hb]')) return true;
  if (line.toLowerCase().includes('debug')) return true;
  return false;
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
    <div class="toast-sub">${isProfit ? t('toast_profit', 'Locked in. New session.') : t('toast_loss', 'Stopped loss. New session.')}</div>
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
    grid.innerHTML = `<div class="shoe-empty">${guiVariant === 'dev' ? '結果待ち...' : 'Waiting for results...'}</div>`;
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
    row.innerHTML = `<div class="daily-empty">${guiVariant === 'dev' ? '履歴なし' : 'No history yet'}</div>`;
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
        setAction(guiVariant === 'dev' ? 'タイ — BET返却' : 'Tie -- BET returned');
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
      // === Phase A1++: 1ハンドごとに round_profit で smooth 更新 ===
      // (旧 A1+ で cumulative_money のみ使用 → 7ハンドに1回しか更新されない問題を修正)
      // round_profit: 各ハンドの BET 額 ($win/-$lose)
      // 1ハンドごとに sessionTotal/daily を更新 → スムーズなUX
      // cumulative_money は status メッセージ受信時の reconciliation 用 (drift 補正)
      if (typeof msg.round_profit === 'number') {
        sessionTotal += msg.round_profit;
        addRoundToDaily(msg.round_profit);
        updateSessionDisplay();
        // _lastCumulativeMoney は次の cumulative_money を基準にする
        if (typeof msg.cumulative_money === 'number') {
          _lastCumulativeMoney = msg.cumulative_money;
        }
        scheduleGuiStateSync();
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

    case 'test_status': {
      // Pattern Test mode: 別カウンタ表示 (sessionPNL等は更新しない)
      const tw = msg.wins || 0;
      const tl = msg.losses || 0;
      const tt = msg.ties || 0;
      const total = tw + tl;
      const wr = total > 0 ? ((tw / total) * 100).toFixed(1) : '0.0';
      const el = $('#testCounter');
      if (el) {
        el.style.display = 'block';
        el.textContent = `🧪 TEST: ${tw}W ${tl}L ${tt}T (${wr}%)`;
      }
      // 視覚フィードバック (フラッシュのみ、PNL は更新しない)
      if (msg.last_won === true) flashScreen('win');
      else if (msg.last_won === false) flashScreen('lose');
      break;
    }

    case 'status': {
      const winLabel = guiVariant === 'dev' ? '勝' : 'W';
      const lossLabel = guiVariant === 'dev' ? '敗' : 'L';
      $('#betCount').textContent = `${msg.wins || 0}${winLabel} / ${msg.losses || 0}${lossLabel}`;
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
      // === Phase A1++: 初回のみ sessionTotal を VPS から同期 (resume時) ===
      // status は定期送信されるため、毎回上書きすると セット途中で sessionTotal が
      // リセットされてしまう。初回のみ同期し、以降は round_profit accumulator に任せる。
      // ドリフト検知: 値が大きく違う場合は警告ログのみ (override しない)
      if (typeof msg.cumulative_money === 'number') {
        if (!_pnlSynced) {
          // 初回のみ同期 (resume直後)
          sessionTotal = msg.cumulative_money;
          _lastCumulativeMoney = msg.cumulative_money;
          _pnlSynced = true;
          updateSessionDisplay();
          addLog(
            format(
              t('log_pnl_synced', 'Session P&L synced from VPS: ${amount}'),
              { amount: `$${sessionTotal >= 0 ? '+' : ''}${sessionTotal.toFixed(2)}` }
            ),
            'info'
          );
        } else {
          // ドリフト検知 (override せず警告のみ)
          const diff = Math.abs(sessionTotal - msg.cumulative_money);
          if (diff > 1.0) {
            // セット途中は cumulative_money が古いので、大きい diff は許容
            // 50以上のズレは異常
            if (diff > 50) {
              console.warn(`[pnl-drift] sessionTotal=${sessionTotal} vs VPS cm=${msg.cumulative_money} (diff=${diff.toFixed(2)})`);
            }
          }
        }
      }
      break;
    }

    case 'session_reset': {
      const amt = msg.amount || 0;
      const isProfit = msg.is_profit;
      const title = isProfit
        ? t('reset_profit', 'PROFIT TARGET HIT')
        : t('reset_loss', 'LOSS CUT');
      const sign = amt >= 0 ? '+' : '-';
      showResetToast(title, `${sign}$${Math.abs(amt).toFixed(0)}`, isProfit);
      flashScreen(isProfit ? 'profit' : 'losscut');
      addLog(`=== ${title} ===  ${sign}$${Math.abs(amt).toFixed(0)}`, isProfit ? 'win' : 'lose');
      // Reset session total (daily total stays)
      // Phase A1+: _lastCumulativeMoney もリセット (次の round_result の delta 計算のため)
      sessionTotal = 0;
      _lastCumulativeMoney = 0;
      updateSessionDisplay();
      break;
    }

    case 'error':
      addLog(guiVariant === 'dev' ? `エラー: ${msg.message}` : `Error: ${msg.message}`, 'lose');
      break;

    case 'stopped':
      // START直後(3秒以内)の stopped は旧プロセスの遅延シグナル→無視
      if (_startedAt && Date.now() - _startedAt < 3000) {
        console.log('[UI] Ignoring stale stopped signal from old process');
        break;
      }
      setRunning(false);
      setAction(guiVariant === 'dev' ? '停止しました' : 'Stopped');
      addLog(t('log_bot_stopped', 'Bot stopped.'));
      syncGuiStateToServer(); // 停止時に即時保存
      break;

    case 'started':
      // 自動再起動 (watchdog / Electron auto-restart) で新しい Python が起動した時
      // ボタン状態 (START disabled / STOP enabled) を再同期
      _startedAt = Date.now();
      setRunning(true);
      setAction(guiVariant === 'dev' ? '自動再起動中' : 'Running (auto-restarted)');
      addLog(guiVariant === 'dev' ? '🔄 自動再起動しました' : '🔄 Bot auto-restarted', 'info');
      break;

    case 'log':
      addLog(msg.message || '');
      break;

    case 'mode_changed':
      if ($('#inputBetMode')) $('#inputBetMode').value = msg.mode || '1drop';
      addLog(`BET mode → ${msg.mode}`, 'info');
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
_lastCumulativeMoney = 0;
results.length = 0;
setRunning(false);
updateSessionDisplay();
setAction(t('action_ready', 'Ready. Press START to begin.'));
addLog(t('log_ready', 'LAPLACE ready. All data cleared.'), 'info');
renderDailyPnl();
renderFeed();
renderRecent();
applyDevMode();
initModalTabs();
initTableFilterControls();
applyTableFilterToUI(loadTableFilter());
