/* LAPLACE User My Page */
(function() {
  const API = location.origin;
  let TOKEN = localStorage.getItem('laplace_user_token') || '';
  let USER_ID = localStorage.getItem('laplace_user_id') || '';
  let activeTab = 'overview';
  let refreshTimer = null;

  const H = () => ({'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json'});

  // Login
  document.getElementById('btn-login').addEventListener('click', doLogin);
  document.getElementById('login-pw').addEventListener('keydown', e => { if (e.key === 'Enter') doLogin(); });

  async function doLogin() {
    const uid = document.getElementById('login-uid').value.trim();
    const pw = document.getElementById('login-pw').value.trim();
    if (!uid || !pw) { alert('Please enter username and password'); return; }
    try {
      const r = await fetch(API + '/api/user/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({user_id: uid, password: pw})
      });
      if (!r.ok) { alert('Invalid username or password'); return; }
      const data = await r.json();
      TOKEN = data.token;
      USER_ID = data.user_id;
      localStorage.setItem('laplace_user_token', TOKEN);
      localStorage.setItem('laplace_user_id', USER_ID);
      showMyPage();
    } catch(e) { alert('Connection error'); }
  }

  document.getElementById('btn-logout').addEventListener('click', () => {
    localStorage.removeItem('laplace_user_token');
    localStorage.removeItem('laplace_user_id');
    TOKEN = ''; USER_ID = '';
    location.reload();
  });

  // Auto-login
  if (TOKEN) {
    fetch(API + '/api/user/me', {headers: H()}).then(r => {
      if (r.ok) showMyPage();
      else { localStorage.removeItem('laplace_user_token'); TOKEN = ''; }
    }).catch(() => {});
  }

  function showMyPage() {
    document.getElementById('login-view').style.display = 'none';
    document.getElementById('mypage-view').style.display = 'block';
    document.getElementById('btn-logout').style.display = 'block';
    document.getElementById('user-name').textContent = USER_ID;
    loadData();
    refreshTimer = setInterval(loadData, 15000);
  }

  // Tabs
  document.querySelectorAll('.admin-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      activeTab = tab.dataset.tab;
      renderTab();
    });
  });

  let cachedData = null;

  async function loadData() {
    try {
      const r = await fetch(API + '/api/user/me', {headers: H()});
      if (!r.ok) return;
      cachedData = await r.json();
      renderMetrics();
      renderTab();
      document.getElementById('last-refresh').textContent = 'Updated: ' + new Date().toLocaleTimeString('ja-JP');
    } catch(e) { console.error(e); }
  }

  function renderMetrics() {
    const d = cachedData;
    if (!d) return;

    // Status banner
    const banner = document.getElementById('status-banner');
    const st = d.status || 'active';
    const bannerColors = {
      active: {bg: 'var(--green-bg)', border: 'var(--green)', text: 'Your BOT is active and running.', icon: '\u2705'},
      free: {bg: 'rgba(59,130,246,0.1)', border: 'var(--accent)', text: 'Free tier - no charges apply.', icon: '\u2B50'},
      grace: {bg: 'var(--yellow-bg)', border: 'var(--yellow)', text: 'Low balance! Please recharge within 24 hours to continue.', icon: '\u26A0\uFE0F'},
      suspended: {bg: 'var(--red-bg)', border: 'var(--red)', text: 'Account suspended. Please recharge to resume.', icon: '\u274C'},
    };
    const b = bannerColors[st] || bannerColors.active;
    banner.innerHTML = `<div style="background:${b.bg};border:1px solid ${b.border};border-radius:10px;padding:14px 20px;display:flex;align-items:center;gap:12px">
      <span style="font-size:1.5em">${b.icon}</span>
      <div><strong style="text-transform:uppercase">${st}</strong><span style="color:var(--text-secondary);margin-left:10px">${b.text}</span></div>
    </div>`;

    // Metric cards
    const sess = d.session || {};
    const m = document.getElementById('metrics');
    m.innerHTML =
      mc('Balance', '$' + (d.balance || 0).toFixed(2), (d.balance || 0) >= 0 ? 'pos' : 'neg') +
      mc('Total Charged', '$' + (d.total_charged || 0).toFixed(2), '') +
      mc('Total Fees Paid', '$' + (d.total_deducted || 0).toFixed(2), '') +
      mc('Bot License', d.bot_paid ? 'Paid ($' + (d.bot_price||0) + ')' : 'Pending', d.bot_paid ? 'pos' : '') +
      (sess.total_bets !== undefined ? mc('Total Bets', sess.total_bets.toString(), '') : '') +
      (sess.win_rate !== undefined ? mc('Win Rate', sess.win_rate + '%', sess.win_rate >= 50 ? 'pos' : 'neg') : '') +
      (sess.cumulative_profit_money !== undefined ? mc('Profit', '$' + fmt$(sess.cumulative_profit_money), sess.cumulative_profit_money >= 0 ? 'pos' : 'neg') : '') +
      mc('Carry Loss', '$' + (d.carry_loss || 0).toFixed(2), (d.carry_loss || 0) > 0 ? 'neg' : '');
  }

  function renderTab() {
    const d = cachedData;
    if (!d) return;
    const panel = document.getElementById('panel-content');

    if (activeTab === 'overview') {
      let html = '<div style="padding:8px">';
      html += '<h3 style="color:var(--text-secondary);margin-bottom:16px">Account Overview</h3>';
      html += '<table class="data-table"><tbody>';
      html += row('Username', d.user_id);
      html += row('Plan', d.bot_price > 0 ? '$' + d.bot_price.toLocaleString() + ' License' : 'Free');
      html += row('Profit Share Rate', (d.profit_share_rate * 100) + '%');
      html += row('Current Balance', '$' + (d.balance || 0).toFixed(2));
      html += row('Account Status', '<span class="badge badge-' + d.status + '">' + d.status.toUpperCase() + '</span>');
      html += row('Member Since', fmtDate(d.created_at));
      const sess = d.session;
      if (sess) {
        html += '<tr><td colspan="2" style="padding-top:20px"><strong style="color:var(--text-secondary)">Session Stats</strong></td></tr>';
        html += row('Total Bets', sess.total_bets);
        html += row('Wins / Losses / Ties', sess.total_wins + ' / ' + sess.total_losses + ' / ' + sess.total_ties);
        html += row('Win Rate', sess.win_rate + '%');
        html += row('Cumulative Profit', '<span class="' + (sess.cumulative_profit_money >= 0 ? 'pos' : 'neg') + '">$' + fmt$(sess.cumulative_profit_money) + '</span>');
        html += row('Sets Completed', sess.sets);
        html += row('Last Activity', fmtTime(sess.updated_at));
      }
      html += '</tbody></table></div>';
      panel.innerHTML = html;
    }
    else if (activeTab === 'history') {
      const charges = (d.charges || []).slice().reverse();
      let html = '<h3 style="color:var(--text-secondary);margin-bottom:12px">Charge History</h3>';
      if (!charges.length) {
        html += '<p style="color:var(--text-muted)">No charges yet.</p>';
      } else {
        html += '<table class="data-table"><thead><tr><th>Date</th><th>Amount</th><th>Note</th></tr></thead><tbody>';
        charges.forEach(c => {
          const cls = c.amount >= 0 ? 'pos' : 'neg';
          html += `<tr><td>${c.date}</td><td class="${cls}">$${c.amount >= 0 ? '+' : ''}${c.amount.toFixed(2)}</td><td style="color:var(--text-muted)">${c.note || '-'}</td></tr>`;
        });
        html += '</tbody></table>';
      }
      panel.innerHTML = html;
    }
    else if (activeTab === 'settlements') {
      const deds = (d.deductions || []).slice().reverse();
      let html = '<h3 style="color:var(--text-secondary);margin-bottom:12px">Daily Settlements</h3>';
      html += '<p style="color:var(--text-muted);font-size:0.85em;margin-bottom:16px">Each day at midnight JST, your profit is calculated. ' +
        (d.profit_share_rate * 100) + '% of net profits are deducted. Losses carry forward to offset future profits.</p>';
      if (!deds.length) {
        html += '<p style="color:var(--text-muted)">No settlements yet.</p>';
      } else {
        html += '<table class="data-table"><thead><tr><th>Date</th><th>Daily P&L</th><th>Fee Deducted</th><th>Carry Loss</th><th>Note</th></tr></thead><tbody>';
        deds.forEach(dd => {
          html += `<tr>
            <td>${dd.date}</td>
            <td class="${dd.daily_profit >= 0 ? 'pos' : 'neg'}">$${fmt$(dd.daily_profit)}</td>
            <td>$${dd.amount.toFixed(2)}</td>
            <td>${dd.carry_loss.toFixed(2)}</td>
            <td style="color:var(--text-muted)">${dd.note || '-'}</td>
          </tr>`;
        });
        html += '</tbody></table>';
      }
      panel.innerHTML = html;
    }
  }

  // Helpers
  function fmt$(v) { return (v >= 0 ? '+' : '') + v.toFixed(2); }
  function fmtTime(iso) {
    if (!iso) return '-';
    const d = new Date(iso), now = new Date(), diff = Math.floor((now - d) / 1000);
    if (diff < 60) return diff + 's ago';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return d.toLocaleDateString('ja-JP');
  }
  function fmtDate(iso) {
    if (!iso) return '-';
    return new Date(iso).toLocaleDateString('en-US', {year:'numeric',month:'short',day:'numeric'});
  }
  function mc(label, value, cls) {
    return `<div class="metric-card"><div class="mc-label">${label}</div><div class="mc-value ${cls}">${value}</div></div>`;
  }
  function row(label, value) {
    return `<tr><td style="color:var(--text-muted);width:200px">${label}</td><td>${value}</td></tr>`;
  }
})();
