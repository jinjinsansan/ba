/* LAPLACE Admin Panel */
(function() {
  const API = location.origin;
  let KEY = localStorage.getItem('laplace_admin_key') || '';
  let activeTab = 'users';
  let refreshTimer = null;

  const H = () => ({'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'});

  // Login
  document.getElementById('btn-login').addEventListener('click', doLogin);
  document.getElementById('admin-key').addEventListener('keydown', e => { if (e.key === 'Enter') doLogin(); });

  async function doLogin() {
    KEY = document.getElementById('admin-key').value.trim();
    if (!KEY) return;
    try {
      const r = await fetch(API + '/api/admin/stats', {headers: H()});
      if (!r.ok) { alert('Invalid admin key'); return; }
      localStorage.setItem('laplace_admin_key', KEY);
      showDashboard();
    } catch(e) { alert('Connection error'); }
  }

  document.getElementById('btn-logout').addEventListener('click', () => {
    localStorage.removeItem('laplace_admin_key');
    KEY = '';
    location.reload();
  });

  // Auto-login
  if (KEY) {
    fetch(API + '/api/admin/stats', {headers: H()}).then(r => {
      if (r.ok) showDashboard(); else { localStorage.removeItem('laplace_admin_key'); KEY = ''; }
    }).catch(() => {});
  }

  function showDashboard() {
    document.getElementById('login-view').style.display = 'none';
    document.getElementById('dashboard-view').style.display = 'block';
    document.getElementById('btn-logout').style.display = 'block';
    loadData();
    refreshTimer = setInterval(loadData, 10000);
  }

  // Tabs
  document.querySelectorAll('.admin-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      activeTab = tab.dataset.tab;
      loadData();
    });
  });

  async function loadData() {
    try {
      if (activeTab === 'users') await loadUsers();
      else if (activeTab === 'orders') await loadOrders();
      else if (activeTab === 'billing') await loadBilling();
      document.getElementById('last-refresh').textContent = 'Updated: ' + new Date().toLocaleTimeString('ja-JP');
    } catch(e) { console.error(e); }
  }

  // ===== Users Tab =====
  async function loadUsers() {
    const r = await fetch(API + '/api/admin/stats', {headers: H()});
    const data = await r.json();
    const users = data.users || [];

    let totalProfit = 0, totalBets = 0, activeCount = 0;
    users.forEach(u => {
      totalProfit += u.cumulative_profit_money;
      totalBets += u.total_bets;
      const b = u.billing;
      if (b && (b.status === 'active' || b.status === 'free')) activeCount++;
    });

    document.getElementById('metrics').innerHTML =
      metricCard('Total P&L', '$' + fmt$(totalProfit), totalProfit >= 0 ? 'pos' : 'neg') +
      metricCard('Total Bets', totalBets.toLocaleString(), '') +
      metricCard('Active Users', activeCount + ' / ' + users.length, '') +
      metricCard('Registered Keys', users.length.toString(), '');

    let html = '<table class="data-table"><thead><tr>' +
      '<th>User</th><th>Status</th><th>Bets</th><th>Win%</th><th>Profit</th>' +
      '<th>Balance</th><th>Carry Loss</th><th>Max Streak</th><th>Sets</th><th>Updated</th>' +
      '</tr></thead><tbody>';
    users.forEach(u => {
      const b = u.billing || {};
      const st = b.status || 'active';
      html += `<tr class="user-row" data-uid="${u.user_id}" style="cursor:pointer">
        <td><strong>${u.user_id}</strong></td>
        <td><span class="badge badge-${st}">${st.toUpperCase()}</span></td>
        <td>${u.total_bets}</td>
        <td>${u.win_rate}%</td>
        <td class="${u.cumulative_profit_money >= 0 ? 'pos' : 'neg'}">$${fmt$(u.cumulative_profit_money)}</td>
        <td class="${(b.balance||0) >= 0 ? 'pos' : 'neg'}">$${(b.balance||0).toFixed(2)}</td>
        <td>${(b.carry_loss||0).toFixed(2)}</td>
        <td>${u.max_loss_streak}</td>
        <td>${u.sets}</td>
        <td>${fmtTime(u.updated_at)}</td>
      </tr>`;
      html += `<tr class="detail-row" id="detail-${u.user_id}" style="display:none">
        <td colspan="10">${renderUserDetail(u)}</td></tr>`;
    });
    html += '</tbody></table>';
    document.getElementById('panel-content').innerHTML = html;

    document.querySelectorAll('.user-row').forEach(row => {
      row.addEventListener('click', () => {
        const uid = row.dataset.uid;
        const dr = document.getElementById('detail-' + uid);
        dr.style.display = dr.style.display === 'none' ? 'table-row' : 'none';
      });
    });
  }

  function renderUserDetail(u) {
    const b = u.billing || {};
    let html = '<div style="padding:16px;background:var(--bg-card);border-radius:8px">';
    html += '<div class="metric-cards" style="margin-bottom:16px">';
    html += metricCard('Bot Price', '$' + (b.bot_price || 0), '') +
            metricCard('Total Charged', '$' + (b.total_charged || 0).toFixed(2), '') +
            metricCard('Total Deducted', '$' + (b.total_deducted || 0).toFixed(2), 'neg') +
            metricCard('Share Rate', ((b.profit_share_rate || 0.2) * 100) + '%', '') +
            metricCard('Chip Base', '$' + u.chip_base, '');
    html += '</div>';
    if (u.api_key) {
      html += `<p style="color:var(--text-muted);font-size:0.82em;margin-bottom:12px">
        API Key: ${u.api_key.prefix} | Rate: ${u.api_key.rate_limit_per_hour}/h | Enabled: ${u.api_key.enabled}</p>`;
    }
    const deds = (b.deductions || []).slice(-20).reverse();
    if (deds.length) {
      html += '<h4 style="color:var(--text-secondary);margin-bottom:8px;font-size:0.88em">Recent Settlements</h4>';
      html += '<table class="data-table"><thead><tr><th>Date</th><th>Daily P&L</th><th>Fee</th><th>Carry</th><th>Note</th></tr></thead><tbody>';
      deds.forEach(d => {
        html += `<tr><td>${d.date}</td><td class="${d.daily_profit >= 0 ? 'pos' : 'neg'}">$${d.daily_profit.toFixed(2)}</td>
          <td>$${d.amount.toFixed(2)}</td><td>${d.carry_loss.toFixed(2)}</td><td style="color:var(--text-muted)">${d.note}</td></tr>`;
      });
      html += '</tbody></table>';
    }
    html += '</div>';
    return html;
  }

  // ===== Orders Tab =====
  async function loadOrders() {
    const r = await fetch(API + '/api/admin/orders', {headers: H()});
    const data = await r.json();
    const orders = data.orders || [];

    const pending = orders.filter(o => o.status === 'pending' || o.status === 'sent').length;
    document.getElementById('metrics').innerHTML =
      metricCard('Total Orders', orders.length.toString(), '') +
      metricCard('Pending', pending.toString(), pending > 0 ? 'neg' : '') +
      metricCard('Confirmed', orders.filter(o => o.status === 'confirmed').length.toString(), 'pos');

    let html = '<table class="data-table"><thead><tr>' +
      '<th>Order ID</th><th>Name</th><th>Plan</th><th>Amount</th><th>Status</th><th>Contact</th><th>Created</th><th>Actions</th>' +
      '</tr></thead><tbody>';
    orders.forEach(o => {
      const badge = o.status === 'confirmed' ? 'badge-confirmed' : o.status === 'sent' ? 'badge-pending' : 'badge-grace';
      html += `<tr>
        <td style="font-family:var(--mono);font-size:0.82em">${o.order_id}</td>
        <td><strong>${o.name}</strong></td>
        <td>${o.plan}</td>
        <td>$${o.amount.toLocaleString()}</td>
        <td><span class="badge ${badge}">${o.status.toUpperCase()}</span></td>
        <td style="color:var(--text-muted)">${o.contact || '-'}</td>
        <td>${fmtTime(o.created_at)}</td>
        <td class="order-actions">`;
      if (o.status !== 'confirmed') {
        html += `<button class="btn-confirm" onclick="confirmOrder('${o.order_id}')">Confirm Payment</button>`;
      } else {
        html += '<span style="color:var(--green)">Done</span>';
      }
      html += '</td></tr>';
    });
    html += '</tbody></table>';
    document.getElementById('panel-content').innerHTML = html;
  }

  // ===== Billing Tab =====
  async function loadBilling() {
    const r = await fetch(API + '/api/admin/billing', {headers: H()});
    const data = await r.json();
    const users = data.users || [];

    let totalBalance = 0, totalDeducted = 0;
    users.forEach(u => { totalBalance += u.balance || 0; totalDeducted += u.total_deducted || 0; });

    document.getElementById('metrics').innerHTML =
      metricCard('Users', users.length.toString(), '') +
      metricCard('Total Balance', '$' + totalBalance.toFixed(2), totalBalance >= 0 ? 'pos' : 'neg') +
      metricCard('Total Collected', '$' + totalDeducted.toFixed(2), 'pos');

    let html = '<table class="data-table"><thead><tr>' +
      '<th>User</th><th>Status</th><th>Bot Price</th><th>Charged</th><th>Balance</th>' +
      '<th>Deducted</th><th>Carry Loss</th><th>Free?</th><th>Actions</th>' +
      '</tr></thead><tbody>';
    users.forEach(u => {
      const st = u.status || 'active';
      html += `<tr>
        <td><strong>${u.user_id}</strong></td>
        <td><span class="badge badge-${st}">${st.toUpperCase()}</span></td>
        <td>$${(u.bot_price||0).toLocaleString()}</td>
        <td>$${(u.total_charged||0).toFixed(2)}</td>
        <td class="${(u.balance||0) >= 0 ? 'pos' : 'neg'}">$${(u.balance||0).toFixed(2)}</td>
        <td>$${(u.total_deducted||0).toFixed(2)}</td>
        <td>${(u.carry_loss||0).toFixed(2)}</td>
        <td>${u.is_free ? '<span class="badge badge-free">FREE</span>' : '-'}</td>
        <td class="order-actions">
          <button class="btn-confirm" onclick="quickCharge('${u.user_id}')">Charge</button>
        </td>
      </tr>`;
    });
    html += '</tbody></table>';

    html += `<div style="margin-top:24px;padding:20px;background:var(--bg-card);border-radius:10px;border:1px solid var(--border)">
      <h4 style="margin-bottom:12px;color:var(--text-secondary)">Register New User</h4>
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:end">
        <div class="form-group" style="margin:0;flex:1;min-width:140px">
          <label>User ID</label>
          <input type="text" id="reg-uid" placeholder="alice">
        </div>
        <div class="form-group" style="margin:0;flex:1;min-width:120px">
          <label>Bot Price ($)</label>
          <input type="number" id="reg-bot" value="1000" min="0">
        </div>
        <div class="form-group" style="margin:0;flex:1;min-width:100px">
          <label>Share Rate</label>
          <input type="number" id="reg-rate" value="0.20" step="0.05" min="0" max="1">
        </div>
        <div class="form-group" style="margin:0;flex:1;min-width:120px">
          <label>Password</label>
          <input type="text" id="reg-pw" placeholder="mypage login">
        </div>
        <div class="form-group" style="margin:0">
          <label>&nbsp;</label>
          <label style="color:var(--text-secondary);font-weight:400;cursor:pointer">
            <input type="checkbox" id="reg-free"> Free User
          </label>
        </div>
        <button class="btn-primary" style="height:42px" onclick="registerUser()">Register</button>
      </div>
    </div>`;

    document.getElementById('panel-content').innerHTML = html;
  }

  // ===== Global Actions =====
  window.confirmOrder = async function(oid) {
    if (!confirm('Confirm payment for order ' + oid + '?')) return;
    const r = await fetch(API + '/api/admin/orders/' + oid + '/confirm', {
      method: 'POST', headers: H()
    });
    if (r.ok) loadData();
    else { const e = await r.json(); alert(e.detail || 'Error'); }
  };

  window.quickCharge = async function(uid) {
    const amount = prompt('Charge amount ($) for ' + uid + ':');
    if (!amount || isNaN(amount) || parseFloat(amount) <= 0) return;
    const r = await fetch(API + '/api/admin/billing/' + uid + '/charge', {
      method: 'POST', headers: H(),
      body: JSON.stringify({amount: parseFloat(amount), note: 'Manual charge via admin panel'})
    });
    if (r.ok) loadData();
    else { const e = await r.json(); alert(e.detail || 'Error'); }
  };

  window.registerUser = async function() {
    const uid = document.getElementById('reg-uid').value.trim();
    if (!uid) { alert('User ID required'); return; }
    const r = await fetch(API + '/api/admin/billing/register', {
      method: 'POST', headers: H(),
      body: JSON.stringify({
        user_id: uid,
        bot_price: parseFloat(document.getElementById('reg-bot').value) || 0,
        profit_share_rate: parseFloat(document.getElementById('reg-rate').value) || 0.20,
        is_free: document.getElementById('reg-free').checked,
        password: document.getElementById('reg-pw').value.trim()
      })
    });
    if (r.ok) { alert('User registered!'); loadData(); }
    else { const e = await r.json(); alert(e.detail || 'Error'); }
  };

  // ===== Helpers =====
  function fmt$(v) { return (v >= 0 ? '+' : '') + v.toFixed(2); }
  function fmtTime(iso) {
    if (!iso) return '-';
    const d = new Date(iso), now = new Date(), diff = Math.floor((now - d) / 1000);
    if (diff < 60) return diff + 's ago';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return d.toLocaleDateString('ja-JP');
  }
  function metricCard(label, value, cls) {
    return `<div class="metric-card"><div class="mc-label">${label}</div><div class="mc-value ${cls}">${value}</div></div>`;
  }
})();
