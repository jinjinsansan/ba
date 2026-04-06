/* LAPLACE Purchase Flow */
(function() {
  const API = location.origin;

  const WALLETS = {
    trc20: '', // Set via /api/config or hardcode
    erc20: ''
  };

  let selectedPlan = null;
  let selectedPrice = 0;
  let currentNet = 'trc20';
  let orderId = null;
  let pollTimer = null;

  // Load wallet config
  fetch(API + '/api/config').then(r => r.json()).then(cfg => {
    if (cfg.wallets) {
      WALLETS.trc20 = cfg.wallets.trc20 || '';
      WALLETS.erc20 = cfg.wallets.erc20 || '';
    }
  }).catch(() => {});

  // Pre-select plan from URL
  const params = new URLSearchParams(location.search);
  const planParam = params.get('plan');
  const orderParam = params.get('order');

  // Plan selection
  document.querySelectorAll('.plan-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.plan-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      selectedPlan = btn.dataset.plan;
      selectedPrice = parseInt(btn.dataset.price);
      updatePreview();
    });
    if (btn.dataset.plan === planParam) btn.click();
  });

  function updatePreview() {
    const amt = parseInt(document.getElementById('charge-amount').value) || 0;
    const el = document.getElementById('balance-preview');
    if (selectedPrice && amt >= selectedPrice) {
      el.textContent = `Starting balance: $${(amt - selectedPrice).toLocaleString()} (after $${selectedPrice.toLocaleString()} license fee)`;
    } else if (selectedPrice && amt > 0) {
      el.textContent = `Minimum charge: $${selectedPrice.toLocaleString()} (to cover license fee)`;
      el.style.color = 'var(--red)';
    } else {
      el.textContent = '';
    }
  }
  document.getElementById('charge-amount').addEventListener('input', updatePreview);

  // Create order
  document.getElementById('btn-create-order').addEventListener('click', async () => {
    if (!selectedPlan) { alert('Please select a plan'); return; }
    const amount = parseInt(document.getElementById('charge-amount').value) || 0;
    if (amount < selectedPrice) { alert(`Minimum charge is $${selectedPrice.toLocaleString()}`); return; }
    const name = document.getElementById('user-name').value.trim();
    if (!name) { alert('Please enter your name'); return; }
    const contact = document.getElementById('user-contact').value.trim();

    try {
      const r = await fetch(API + '/api/orders', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ plan: selectedPlan, amount, name, contact })
      });
      if (!r.ok) { const e = await r.json(); alert(e.detail || 'Error'); return; }
      const data = await r.json();
      orderId = data.order_id;
      showPaymentStep(data);
    } catch(e) { alert('Connection error: ' + e); }
  });

  function showPaymentStep(data) {
    document.getElementById('step-plan').style.display = 'none';
    document.getElementById('step-payment').style.display = 'block';
    document.getElementById('pay-amount').textContent = '$' + data.amount.toLocaleString();
    document.getElementById('order-id').textContent = data.order_id;
    document.getElementById('order-plan').textContent = data.plan;
    document.getElementById('order-charge').textContent = data.amount.toLocaleString();
    showWallet(currentNet);
  }

  // Network tabs
  document.querySelectorAll('.network-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.network-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      currentNet = tab.dataset.net;
      showWallet(currentNet);
    });
  });

  function showWallet(net) {
    const addr = WALLETS[net] || 'Wallet address not configured';
    document.getElementById('wallet-addr').textContent = addr;
    document.getElementById('net-label').textContent =
      net === 'trc20' ? 'TRON Network (Low fees)' : 'Ethereum Network';
  }

  // Copy
  document.getElementById('btn-copy').addEventListener('click', () => {
    const addr = document.getElementById('wallet-addr').textContent;
    navigator.clipboard.writeText(addr).then(() => {
      document.getElementById('btn-copy').textContent = 'Copied!';
      setTimeout(() => document.getElementById('btn-copy').textContent = 'Copy Address', 2000);
    });
  });

  // Mark as sent
  document.getElementById('btn-sent').addEventListener('click', async () => {
    if (!orderId) return;
    try {
      await fetch(API + '/api/orders/' + orderId + '/sent', { method: 'POST' });
    } catch(e) {}
    showStatusStep();
  });

  function showStatusStep() {
    document.getElementById('step-payment').style.display = 'none';
    document.getElementById('step-status').style.display = 'block';
    document.getElementById('status-order-id').textContent = orderId;
    startPolling();
  }

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(checkStatus, 8000);
    checkStatus();
  }

  async function checkStatus() {
    if (!orderId) return;
    try {
      const r = await fetch(API + '/api/orders/' + orderId);
      if (!r.ok) return;
      const data = await r.json();
      if (data.status === 'confirmed') {
        clearInterval(pollTimer);
        document.getElementById('status-icon').textContent = '\u2705';
        document.getElementById('status-text').textContent = 'Payment Confirmed!';
        document.getElementById('status-sub').innerHTML =
          'Your account is now active. You will receive your LAPLACE client via ' +
          (data.contact || 'your provided contact') + '.<br><br>' +
          '<strong>Thank you for choosing LAPLACE.</strong>';
      } else if (data.status === 'sent') {
        document.getElementById('status-text').textContent = 'Payment Sent - Awaiting Confirmation';
      }
    } catch(e) {}
  }

  // Resume if order param in URL
  if (orderParam) {
    orderId = orderParam;
    document.getElementById('step-plan').style.display = 'none';
    showStatusStep();
  }
})();
