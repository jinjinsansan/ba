// ba GUI v2 — Copilot フロントエンド

const $ = (id) => document.getElementById(id);

async function api(path, opts = {}) {
  const res = await fetch(path, {
    method: opts.method || 'GET',
    headers: { 'Content-Type': 'application/json' },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  return res.json();
}

// ============== セッション操作 ==============

$('btnStart').addEventListener('click', async () => {
  const tname = $('tableName').value.trim();
  await api('/api/session/start', { method: 'POST', body: { table_name: tname } });
  refresh();
});

$('btnStop').addEventListener('click', async () => {
  await api('/api/session/stop', { method: 'POST' });
  refresh();
});

$('btnExitTable').addEventListener('click', async () => {
  if (!confirm('このテーブルから退室しますか? (Camoufox で手動退室後にクリック)')) return;
  await api('/api/session/exit_table', { method: 'POST' });
  refresh();
  refreshSlow();
});

// pending BET 手動解決
async function resolvePending(outcome) {
  const r = await api('/api/bet/manual_resolve', { method: 'POST', body: { outcome } });
  if (!r.ok) alert(r.error || '解決失敗');
  refresh();
}
$('btnPendingWin')  && $('btnPendingWin').addEventListener('click',  () => resolvePending('win'));
$('btnPendingLose') && $('btnPendingLose').addEventListener('click', () => resolvePending('lose'));
$('btnPendingTie')  && $('btnPendingTie').addEventListener('click',  () => resolvePending('tie'));

// ============== Scraper 制御 ==============

$('btnScraperStart').addEventListener('click', async () => {
  const r = await api('/api/scraper/start', { method: 'POST' });
  if (!r.ok) alert(r.error || 'start 失敗');
  refreshScraperStatus();
});

$('btnScraperStop').addEventListener('click', async () => {
  const r = await api('/api/scraper/stop', { method: 'POST' });
  refreshScraperStatus();
});

// autoFollow は click-to-focus で自動 ON になるため UI から削除

// btnSyncTable 削除済 (click-to-focus が sync を兼ねる)

$('btnManualLogin').addEventListener('click', async () => {
  const msg = '別ウィンドウで Camoufox が起動します。\n\n' +
    '手順:\n' +
    '1. Stake.com にログイン\n' +
    '2. バカラロビーに移動してテーブル一覧が表示されることを確認\n' +
    '3. 30 秒以上待機 (cookie 完全保存のため)\n' +
    '4. ブラウザを閉じる (×ボタン)\n\n' +
    '起動しますか? (scraper が稼働中の場合は先に停止)';
  if (!confirm(msg)) return;
  const r = await api('/api/scraper/manual_login', { method: 'POST' });
  if (!r.ok) alert(r.error || 'manual_login 起動失敗');
  else alert('別ウィンドウで Camoufox が起動しました。ブラウザを閉じたら scraper を起動してください。');
});

async function refreshScraperStatus() {
  try {
    const s = await api('/api/scraper/status');
    const el = $('scraperStatus');
    const btnStart = $('btnScraperStart');
    const btnStop  = $('btnScraperStop');
    el.className = 'scraper-state';
    if (!s.running) {
      el.classList.add('stopped');
      el.textContent = '● OFFLINE';
      btnStart.textContent = '▶ 起動';
      btnStart.classList.remove('active');
      btnStop.style.display = 'none';
    } else if (s.status && s.status.startsWith('failed')) {
      el.classList.add('error');
      el.textContent = '● ERROR';
      el.title = s.last_error || s.status;
      btnStart.textContent = '▶ 再起動';
      btnStart.classList.remove('active');
      btnStop.style.display = '';
    } else if (s.status === 'running' || (s.status && s.status.startsWith('running'))) {
      el.classList.add('running');
      el.textContent = `● ONLINE`;
      btnStart.textContent = '⬤ 起動中';
      btnStart.classList.add('active');
      btnStop.style.display = '';
    } else {
      el.classList.add('booting');
      el.textContent = `● 起動中...`;
      btnStart.textContent = '⬤ 起動中...';
      btnStart.classList.add('active');
      btnStop.style.display = '';
    }
    el.title = `status: ${s.status || '?'}\nlast_error: ${s.last_error || 'none'}`;
  } catch (e) {
    console.error(e);
  }
}

// ============== AI 学習パネル ==============

async function refreshLearning() {
  try {
    const s = await api('/api/learning/stats');
    $('learnBets').textContent = s.total_bets.toLocaleString();
    $('learnWinRate').textContent = s.total_bets > 0 ? s.overall_win_rate.toFixed(1) + '%' : '-';
    const n = s.total_bets;
    $('learnStatus').textContent = n === 0 ? '待機' : n < 10 ? `収集中 (${n})` : n < 50 ? `学習初期 (${n})` : `補正中 (${n})`;

    const renderRow = (key, d) => {
      const cls = d.win_rate >= 52 ? 'good' : d.win_rate < 48 ? 'bad' : '';
      const pct = Math.min(Math.max(d.win_rate, 0), 100);
      return `
        <div class="learn-row">
          <span class="learn-key">${key}</span>
          <span class="learn-n">n=${d.bets}</span>
          <span class="learn-wr ${cls}">${d.win_rate.toFixed(1)}%</span>
          <span class="learn-bar"><span class="learn-bar-fill" style="width:${pct}%"></span></span>
        </div>`;
    };
    $('learnPatterns').innerHTML = s.per_pattern.map(d => renderRow(d.key, d)).join('') || '<div style="color:var(--text-muted);font-size:11px;padding:6px">データなし</div>';
    $('learnTables').innerHTML = s.per_table.map(d => renderRow(d.key, d)).join('') || '<div style="color:var(--text-muted);font-size:11px;padding:6px">データなし</div>';
  } catch (e) {
    console.error(e);
  }
}

// ============== Hand 入力 ==============

document.querySelectorAll('.hand-btn[data-result]').forEach(btn => {
  btn.addEventListener('click', async () => {
    const result = btn.dataset.result;
    await api('/api/hand', { method: 'POST', body: { result } });
    refresh();
  });
});

$('btnUndo').addEventListener('click', async () => {
  await api('/api/hand/undo', { method: 'POST' });
  refresh();
});

// ============== キーボードショートカット ==============

document.addEventListener('keydown', async (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  const k = e.key.toLowerCase();
  if (k === 'p') document.querySelector('.hand-btn[data-result="P"]')?.click();
  else if (k === 'b') document.querySelector('.hand-btn[data-result="B"]')?.click();
  else if (k === 't') document.querySelector('.hand-btn[data-result="T"]')?.click();
  else if (k === 'u' || k === 'backspace') { e.preventDefault(); $('btnUndo')?.click(); }
});

// ============== 描画 ==============

function renderWatchlist(wl) {
  const mkItem = (t, cls) => `
    <li class="${cls}">
      <div class="name">${t.name}</div>
    </li>`;
  const mkBlack = (n) => `<li class="red"><div class="name">${n}</div></li>`;
  $('wlConfirmed').innerHTML = wl.confirmed.map(t => mkItem(t, 'green')).join('');
  $('wlExpected').innerHTML = wl.expected.map(t => mkItem(t, 'yellow')).join('');
  $('wlBlack').innerHTML = wl.blacklist.map(mkBlack).join('');
}

// ============== タブ切替 ==============

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
    $('lobbyLive').classList.toggle('active', tab === 'live');
    $('lobbyWl').classList.toggle('active', tab === 'wl');
  });
});

// ============== Lobby Live ==============

let currentTable = '';

const _lobbyPrevState = {};  // table → {n_hands, pattern, entry_ok}

const patCls = (p) => {
  if (p === '縦流れ') return 'good';
  if (p === '横流れ') return 'good';
  if (p === '不規則') return 'bad';
  return 'warn';
};

function renderLobbyLive(lobby, focusedTableName) {
  const container = $('lobbyCards') || $('lobbyList');
  if (!container) return;

  if (!lobby || !lobby.tables) {
    container.innerHTML = '<div class="tbl-card empty"><div class="tc-name">データなし</div></div>';
    $('lobbySource').textContent = 'n/a';
    return;
  }

  // ソース表示
  const src = lobby.source === 'live'
    ? `🟢 live${lobby.ws_connected ? ' WS-OK' : ' WS-wait'}`
    : lobby.source === 'scraper'
      ? `scraper (${(lobby.updated_at||'').substr(11,8)})`
      : lobby.source === 'db'
        ? `DB (${(lobby.db_latest||'').substr(0,16).replace('T',' ')})`
        : lobby.source;
  $('lobbySource').textContent = src;

  // メータ
  const total = lobby.tables.length;
  const loaded = lobby.tables.filter(t => t.n_hands > 0).length;
  const wlLoaded = lobby.tables.filter(t => t.in_whitelist && t.n_hands > 0).length;
  const entryOk = lobby.tables.filter(t => t.entry_ok).length;
  const meterEl = $('lobbyMeter');
  if (meterEl) {
    const pct = total ? Math.round(loaded / total * 100) : 0;
    meterEl.innerHTML = `
      <div class="meter-bar"><div class="meter-fill" style="width:${pct}%"></div></div>
      <div class="meter-text">
        <span>📡 ${loaded}/${total}</span>
        <span>⭐ WL: ${wlLoaded}/8</span>
        <span>🟢 Entry: ${entryOk}</span>
      </div>`;
  }

  // ソート: entry_ok > WL > loaded > その他, BL は末尾
  const sorted = [...lobby.tables].sort((a, b) => {
    if (a.in_blacklist !== b.in_blacklist) return a.in_blacklist - b.in_blacklist;
    if (a.entry_ok !== b.entry_ok) return b.entry_ok - a.entry_ok;
    if (a.in_whitelist !== b.in_whitelist) return b.in_whitelist - a.in_whitelist;
    if ((a.n_hands > 0) !== (b.n_hands > 0)) return (b.n_hands > 0) - (a.n_hands > 0);
    return b.score - a.score;
  });

  // 差分検知
  const changed = new Set();
  const newTables = new Set();
  for (const t of sorted) {
    const prev = _lobbyPrevState[t.table];
    if (!prev) {
      newTables.add(t.table);
    } else if (prev.n_hands !== t.n_hands || prev.pattern !== t.pattern || prev.entry_ok !== t.entry_ok) {
      changed.add(t.table);
    }
    _lobbyPrevState[t.table] = { n_hands: t.n_hands, pattern: t.pattern, entry_ok: t.entry_ok };
  }

  container.innerHTML = sorted.map(t => {
    const classes = ['tbl-card'];
    if (t.in_whitelist) classes.push('wl');
    if (t.in_blacklist) classes.push('bl');
    if (t.table === focusedTableName) classes.push('focused');
    if (newTables.has(t.table)) classes.push('flash-new');
    else if (changed.has(t.table)) classes.push('flash-update');
    if (t.n_hands === 0) classes.push('empty');
    if (t.entry_ok && t.n_hands > 0) classes.push('entry-hot');

    const wlMark = t.in_whitelist ? '<span class="wl-star">⭐</span>' : '';
    const playersMark = t.players > 0 ? `<span class="players">👥${t.players}</span>` : '';
    const blead = t.b_lead !== undefined ? `(${t.b_lead >= 0 ? '+' : ''}${t.b_lead})` : '';
    const entryBadge = t.entry_ok && t.n_hands > 0 ? '<span class="tc-entry-badge">🟢 BET OK</span>' : '';
    const hintText = t.table === focusedTableName ? '👀 フォーカス中' : 'クリックで監視開始';

    return `
      <div class="${classes.join(' ')}" data-table="${t.table.replace(/"/g,'&quot;')}">
        <div class="tc-top">
          <div class="tc-name">${t.table}${wlMark}${playersMark}</div>
          ${entryBadge}
        </div>
        <div class="tc-middle">
          <span class="pat-tag ${patCls(t.pattern)}">${t.pattern === '不明' ? '📡 収集中' : t.pattern}</span>
          ${t.sub ? `<span class="pat-tag warn">${t.sub}</span>` : ''}
          <span class="hand-chip">${t.n_hands}h</span>
          <span class="col-chip">${t.n_cols}列</span>
          <span class="col-chip">P${t.p_cnt}:${t.b_cnt}B${blead}</span>
        </div>
        <div class="tc-bottom">
          <span>${t.pattern === '不明' ? `手数蓄積中 (${t.n_cols}/5列)` : (t.pattern_reason || '')}</span>
          <span class="click-hint">${hintText}</span>
        </div>
      </div>`;
  }).join('') || '<div class="tbl-card empty"><div class="tc-name">直近で稼働中のテーブルなし</div></div>';

  // クリック → focus table API 呼び出し
  document.querySelectorAll('#lobbyCards .tbl-card[data-table]').forEach(card => {
    card.addEventListener('click', async () => {
      const tn = card.dataset.table;
      if (!tn) return;

      if (card.classList.contains('bl')) {
        if (!confirm(`⚠️ ${tn} は回収テーブル (blacklist) です。\n本当にこのテーブルに入りますか?`)) return;
      }

      card.classList.add('flash-click');
      setTimeout(() => card.classList.remove('flash-click'), 400);

      const r = await api('/api/session/focus_table', { method: 'POST', body: { table_name: tn } });
      if (!r.ok) {
        alert(r.error || 'フォーカス失敗');
        return;
      }
      refresh();
      refreshSlow();
    });
  });
}

function renderBigRoad(canvas, seq) {
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.fillStyle = '#0a1020';
  ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = '#1e2838';
  ctx.lineWidth = 1;
  const cellSize = 18;
  const cols = Math.floor(W / cellSize);
  const rows = Math.floor(H / cellSize);
  for (let x = 0; x <= cols; x++) {
    ctx.beginPath(); ctx.moveTo(x * cellSize, 0); ctx.lineTo(x * cellSize, H); ctx.stroke();
  }
  for (let y = 0; y <= rows; y++) {
    ctx.beginPath(); ctx.moveTo(0, y * cellSize); ctx.lineTo(W, y * cellSize); ctx.stroke();
  }

  // 大路: 縦落ち → ドラゴンターン
  let col = 0, row = 0;
  let lastSide = null;
  let bottomRow = 0;
  for (const ch of seq) {
    if (ch === 'T') continue;
    if (ch !== lastSide) {
      if (lastSide !== null) { col++; row = 0; bottomRow = 0; }
      lastSide = ch;
    } else {
      row++;
      if (row >= rows) { col++; /* dragon tail */ row = rows - 1; }
    }
    const cx = col * cellSize + cellSize / 2;
    const cy = row * cellSize + cellSize / 2;
    ctx.beginPath();
    ctx.arc(cx, cy, cellSize / 2 - 2, 0, Math.PI * 2);
    ctx.strokeStyle = ch === 'P' ? '#3b82f6' : '#dc2626';
    ctx.lineWidth = 2;
    ctx.stroke();
  }
}

function renderHandHistory(history) {
  const box = $('handHistory');
  box.innerHTML = history.map(h => {
    const cls = h.result === 'P' ? 'h-P' : h.result === 'B' ? 'h-B' : 'h-T';
    const br = h.bet_resolved;
    const res = br ? (br.won ? 'won' : 'lost') : '';
    return `<div class="h-cell ${cls} ${res}" title="${h.time} ${h.result}${br ? ' BET ' + br.side + (br.won ? ' WIN' : ' LOSE') : ''}">${h.result}</div>`;
  }).join('');
}

function renderAI(data) {
  const info = data.info;
  const enter = data.enter_check;
  const bet = data.bet_recommend;
  const pattern = info.pattern;

  const patEl = $('aiPattern');
  patEl.textContent = pattern;
  patEl.className = 'val-big';
  if (['縦面5+密集', '縦面4以下密集', 'ニコニコ・ニコイチ'].includes(pattern)) {
    patEl.classList.add('bet-ok');
  } else if (['不規則', 'ブリッジ', '偏り'].includes(pattern)) {
    patEl.classList.add('bet-bad');
  } else {
    patEl.classList.add('bet-no');
  }
  $('aiPatternReason').textContent = info.reason || '-';

  const entEl = $('aiEntry');
  if (data.entered) {
    entEl.textContent = `✅ 入室中 — ${data.entry_pattern}`;
    entEl.className = 'val-big ok';
    $('aiEntryReason').textContent = `退室シグナル待ち`;
  } else if (enter.flag) {
    entEl.textContent = `⏩ 入室 OK`;
    entEl.className = 'val-big ok';
    $('aiEntryReason').textContent = enter.reason;
  } else {
    entEl.textContent = `⏸ 未入室`;
    entEl.className = 'val-big no';
    $('aiEntryReason').textContent = enter.reason;
  }

  const actEl = $('aiBetAction');
  if (bet.action === 'BET') {
    actEl.textContent = `🟢 BET ${bet.side}`;
    actEl.className = 'val-big bet';
  } else if (bet.action === 'LOOK') {
    actEl.textContent = `🟡 LOOK`;
    actEl.className = 'val-big look';
  } else {
    actEl.textContent = `🔴 EXIT`;
    actEl.className = 'val-big exit';
  }
  $('aiBetReason').textContent = bet.reason;

  const unit = data.next_unit || 1;
  $('aiBetAmount').textContent = `$${unit}`;
  $('aiUnitIdx').textContent = data.session.current_unit_idx;

  // === Forecast ===
  const fc = data.forecast || {};
  const levelMap = {
    imminent: { label: '🔥 狙い目!', cls: 'imminent' },
    reach:    { label: '🎯 リーチ前リーチ', cls: 'reach' },
    watching: { label: '👁️ 観察中', cls: 'watching' },
    waiting:  { label: '⏳ 判定待ち', cls: 'waiting' },
    exit:     { label: '🚪 退室推奨', cls: 'exit' },
    pending:  { label: '💰 BET 実行中', cls: 'pending' },
  };
  const lv = levelMap[fc.level] || { label: '-', cls: 'watching' };
  const lvEl = $('fcLevel');
  lvEl.className = 'fc-level ' + lv.cls;
  lvEl.textContent = lv.label;
  // forecast が exit レベルの時に退室ボタンを点滅
  const exitBtn = $('btnExitTable');
  if (exitBtn) exitBtn.classList.toggle('ai-exit-hint', fc.level === 'exit');
  $('fcSituation').textContent = fc.situation || '-';
  $('fcNext').textContent = fc.next || '-';
  if (fc.confidence !== null && fc.confidence !== undefined) {
    $('fcConfRow').style.display = 'flex';
    $('fcConfFill').style.width = fc.confidence + '%';
    $('fcConfPct').textContent = fc.confidence + '%';
    // 履歴加重が効いているなら補足表示
    const lrn = fc.learning;
    const fcLrnEl = document.getElementById('fcLearnInfo');
    if (lrn && lrn.hist_n > 0 && fcLrnEl) {
      fcLrnEl.innerHTML = `🧠 learned: rule ${lrn.rule_conf}% → hist ${lrn.hist_rate}% (n=${lrn.hist_n}) → blended ${lrn.blended}%`;
      fcLrnEl.style.display = 'block';
    } else if (fcLrnEl) {
      fcLrnEl.style.display = 'none';
    }
  } else {
    $('fcConfRow').style.display = 'none';
  }

  // === Pending BET resolver ===
  const pb = data.pending_bet;
  const pendingBlock = $('aiPendingBlock');
  if (pb && pb.side) {
    pendingBlock.style.display = 'block';
    $('aiPendingDetails').innerHTML = `BET: <b>${pb.side}</b> $${pb.unit.toFixed(0)} <span style="color:#8a96a8;font-weight:400;font-size:11px">(${pb.pattern})</span>`;
  } else {
    pendingBlock.style.display = 'none';
  }

  const f = info.features || {};
  $('feat5plus').textContent = f.n_long5 ?? 0;
  $('feat4plus').textContent = f.n_long4 ?? 0;
  $('featLe2').textContent = (f.pct_le2 ?? 0) + '%';
  $('featSingleRun').textContent = f.single_run ?? 0;
  $('featTrailing').textContent = f.trailing_ones ?? 0;
  $('featOvershoot').textContent = data.session.overshoot ?? 0;
}

function renderKPI(s) {
  // SESSION ボタン状態
  const btnStart = $('btnStart');
  const btnStop  = $('btnStop');
  if (s.active) {
    btnStart.textContent = '⬤ セッション中';
    btnStart.classList.add('active');
    btnStop.style.display = '';
  } else {
    btnStart.textContent = '▶ SESSION';
    btnStart.classList.remove('active');
    btnStop.style.display = 'none';
  }

  $('kpiWinRate').textContent = s.bets > 0 ? s.win_rate.toFixed(1) + '%' : '-';
  $('kpiWlCount').textContent = `${s.wins}勝 ${s.losses}負 / ${s.bets} bets`;
  $('kpiPnl').textContent = `$${s.pnl >= 0 ? '+' : ''}${s.pnl}`;
  $('kpiStake').textContent = `stake $${s.stake}`;
  $('kpiRoi').textContent = (s.roi >= 0 ? '+' : '') + s.roi.toFixed(2) + '%';
  $('kpiUnit').textContent = `$${s.current_unit}`;
  $('kpiSetTurn').textContent = `set ${s.sets_completed + 1} / turn ${s.current_turn}/7`;
  $('kpiOvershoot').textContent = s.overshoot;
  $('kpiSets').textContent = s.sets_completed;

  // カード色: 勝率
  const wrCard = $('kpiWinRate').parentElement;
  wrCard.classList.remove('good', 'bad');
  if (s.bets >= 3) {
    if (s.win_rate >= 52) wrCard.classList.add('good');
    else if (s.win_rate < 48) wrCard.classList.add('bad');
  }
  const pnlCard = $('kpiPnl').parentElement;
  pnlCard.classList.remove('good', 'bad');
  if (s.pnl > 0) pnlCard.classList.add('good');
  else if (s.pnl < 0) pnlCard.classList.add('bad');
  const roiCard = $('kpiRoi').parentElement;
  roiCard.classList.remove('good', 'bad');
  if (s.roi > 2) roiCard.classList.add('good');
  else if (s.roi < -2) roiCard.classList.add('bad');

  $('tableDisplay').textContent = s.table
    ? `${s.table} ${s.active ? '👀 監視中' : '■'}`
    : (s.active ? '📡 テーブル未フォーカス — カードをクリックして選択' : '未開始');
  $('metaHands').textContent = s.hands;
  // Exit ボタンは focused 中のみ enable
  const exitBtn = $('btnExitTable');
  if (exitBtn) exitBtn.disabled = !s.table;
}

function renderShoeMeta(info) {
  $('metaCols').textContent = info.n_cols;
  $('metaP').textContent = info.p_cnt;
  $('metaB').textContent = info.b_cnt;
  $('metaT').textContent = info.t_cnt;
  $('metaBLead').textContent = info.b_lead >= 0 ? '+' + info.b_lead : info.b_lead;
}

function renderLog(log) {
  const box = $('actionLog');
  box.innerHTML = log.slice().reverse().map(r => `
    <div class="row">
      <div class="time">${r.time}</div>
      <div class="kind kind-${r.kind}">${r.kind}</div>
      <div class="msg">${r.msg}</div>
    </div>
  `).join('');
}

// ============== Charts (SVG) ==============

function renderEquityChart(points) {
  const box = $('chartEquity');
  if (!points.length) { box.innerHTML = '<div style="color:#666;padding:20px;text-align:center">BET 履歴なし</div>'; return; }
  const W = 520, H = 120, pad = 24;
  const xs = points.map(p => p.i);
  const ys = points.map(p => p.pnl);
  const xmin = 0, xmax = Math.max(...xs, 1);
  const ymin = Math.min(...ys, 0);
  const ymax = Math.max(...ys, 0);
  const yrange = Math.max(ymax - ymin, 1);
  const x = v => pad + (v - xmin) / Math.max(xmax - xmin, 1) * (W - 2 * pad);
  const y = v => H - pad - (v - ymin) / yrange * (H - 2 * pad);
  const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.i).toFixed(1)},${y(p.pnl).toFixed(1)}`).join(' ');
  const zero_y = (ymin <= 0 && ymax >= 0) ? y(0) : null;
  const color = (ys[ys.length - 1] >= 0) ? '#4ade80' : '#f87171';
  const dots = points.map(p =>
    `<circle cx="${x(p.i).toFixed(1)}" cy="${y(p.pnl).toFixed(1)}" r="2" fill="${p.won ? '#4ade80' : '#f87171'}" />`
  ).join('');
  box.innerHTML = `
<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
  <rect x="0" y="0" width="${W}" height="${H}" fill="#0a1020"/>
  ${zero_y !== null ? `<line x1="${pad}" y1="${zero_y}" x2="${W-pad}" y2="${zero_y}" stroke="#475569" stroke-dasharray="3,3"/>` : ''}
  <path d="${path}" fill="none" stroke="${color}" stroke-width="2"/>
  ${dots}
  <text x="${pad}" y="14" fill="#8a96a8" font-size="10" font-family="monospace">PNL ${ymin.toFixed(0)} 〜 ${ymax.toFixed(0)} | BETs ${xmax}</text>
</svg>`;
}

function renderWinRateChart(points) {
  const box = $('chartWinRate');
  if (!points.length) { box.innerHTML = '<div style="color:#666;padding:20px;text-align:center">BET 履歴なし</div>'; return; }
  const W = 520, H = 120, pad = 24;
  const xs = points.map(p => p.i);
  const xmin = 0, xmax = Math.max(...xs, 1);
  const ymin = 40, ymax = 60;
  const x = v => pad + (v - xmin) / Math.max(xmax - xmin, 1) * (W - 2 * pad);
  const y = v => H - pad - (Math.max(Math.min(v, ymax), ymin) - ymin) / (ymax - ymin) * (H - 2 * pad);
  const line52 = y(52);
  const line50 = y(50);
  const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.i).toFixed(1)},${y(p.wr).toFixed(1)}`).join(' ');
  const lastWr = points[points.length - 1].wr;
  const color = lastWr >= 52 ? '#4ade80' : lastWr >= 48 ? '#fbbf24' : '#f87171';
  box.innerHTML = `
<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
  <rect x="0" y="0" width="${W}" height="${H}" fill="#0a1020"/>
  <line x1="${pad}" y1="${line50}" x2="${W-pad}" y2="${line50}" stroke="#475569" stroke-dasharray="3,3"/>
  <text x="${W-pad-4}" y="${line50-3}" fill="#8a96a8" font-size="9" font-family="monospace" text-anchor="end">50%</text>
  <line x1="${pad}" y1="${line52}" x2="${W-pad}" y2="${line52}" stroke="#4ade80" stroke-dasharray="3,3" opacity="0.6"/>
  <text x="${W-pad-4}" y="${line52-3}" fill="#4ade80" font-size="9" font-family="monospace" text-anchor="end">52% (目標)</text>
  <path d="${path}" fill="none" stroke="${color}" stroke-width="2"/>
  <text x="${pad}" y="14" fill="#8a96a8" font-size="10" font-family="monospace">現在 ${lastWr.toFixed(1)}% | n=${xmax}</text>
</svg>`;
}

// ============== Refresh loop ==============

async function refresh() {
  try {
    const data = await api('/api/status');
    renderWatchlist(data.watchlist);
    renderBigRoad($('bigRoad'), data.seq);
    renderHandHistory(data.hand_history);
    renderAI(data);
    renderKPI(data.session);
    renderShoeMeta(data.info);
    renderLog(data.action_log);
    currentTable = data.session.table;
  } catch (e) {
    console.error(e);
  }
}

async function refreshSlow() {
  // Lobby + charts: 重いので 5 秒間隔
  try {
    const hours = ($('lobbyHours') && $('lobbyHours').value) || '4';
    const [lobby, chart] = await Promise.all([
      api('/api/lobby?hours=' + hours),
      api('/api/session/chart_data'),
    ]);
    renderLobbyLive(lobby, currentTable);
    renderEquityChart(chart.equity);
    renderWinRateChart(chart.win_rate);
  } catch (e) {
    console.error(e);
  }
}

// ページ読み込み時: ボタン初期化 → リセット → 描画開始 (順番を保証)
(async function initPage() {
  // ① ボタンを初期状態に
  const bs = $('btnScraperStart'); const bx = $('btnScraperStop');
  const bn = $('btnStart');        const bt = $('btnStop');
  if (bs) { bs.textContent = '▶ 起動'; bs.classList.remove('active'); }
  if (bx) bx.style.display = 'none';
  if (bn) { bn.textContent = '▶ SESSION'; bn.classList.remove('active'); }
  if (bt) bt.style.display = 'none';

  // ② 残留セッションをサーバー側で完全リセット
  try { await api('/api/session/reset', { method: 'POST' }); } catch(e) {}

  // ③ DOM を直接クリア（サーバー応答を待たず即反映）
  const clearIds = ['handHistory','bigRoad','actionLog','kpiWinRate','kpiWlCount',
    'kpiPnl','kpiStake','kpiRoi','kpiUnit','kpiSetTurn','kpiOvershoot','kpiSets',
    'currentTableName','seqDisplay'];
  clearIds.forEach(id => { const el = $(id); if (el) el.innerHTML = ''; });
  const tblName = $('currentTableName');
  if (tblName) tblName.textContent = '—';

  // ④ リセット後に描画開始
  refresh();
  refreshSlow();
  refreshScraperStatus();
  refreshLearning();
  setInterval(refresh, 1500);
  setInterval(refreshSlow, 2000);
  setInterval(refreshScraperStatus, 3000);
  setInterval(refreshLearning, 8000);
})();
