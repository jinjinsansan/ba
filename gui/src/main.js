// LAPLACE Electron main (Fat Client)
//
// Architecture (正):
//   Local PC / Desktop Cloud:
//     - Electron GUI (this window)
//     - Python agent (agent_api.py) spawned as child process
//     - VISIBLE Camoufox browser (you can watch each BET happen)
//     - BetExecutor physically clicks BET buttons on Stake
//   VPS:
//     - laplace-api.service (MaruBatsu logic engine) — no browser
//     - laplace-collector.service (62 tables data warehouse)
//
// Flow on Start:
//   1. Open SSH tunnel (127.0.0.1:8000 -> VPS:8000)
//   2. Spawn Python agent_api.py with merged .env
//   3. Python agent launches visible Camoufox and uses RemoteLaplaceSession
//      to delegate logic decisions to the VPS API
//   4. GUI receives stdin/stdout JSON IPC events (action, round_result, ...)

const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn } = require('child_process');
const https = require('https');
const { shell } = require('electron');

// EPIPE/broken pipe防止: 子プロセスのパイプが切れてもクラッシュしない
process.on('uncaughtException', (err) => {
  if (err.code === 'EPIPE' || err.code === 'ERR_STREAM_DESTROYED') {
    console.error('[Main] Suppressed EPIPE:', err.message);
    return;
  }
  console.error('[Main] Uncaught exception:', err);
});

let mainWindow = null;
let pythonProcess = null;
let sshTunnelProcess = null;
let supportTunnelProcess = null;
let statusInterval = null;

// === Auto-Restart on Browser/Python Crash ===
// Camoufox がクラッシュ → Python が "Target page closed" 検知 → exit
// → close handler が "stopped" を送信 → GUI が STOPPED 表示
// この時に自動で Python を再起動する仕組み。
// userInitiatedStop=false (= 予期しない終了) かつ lastStartConfig がある場合のみ自動再開。
let userInitiatedStop = false;
let lastStartConfig = null;
let autoRestartCount = 0;
let lastSpawnAt = 0;
const MAX_AUTO_RESTARTS = 10;       // 連続失敗上限
const AUTO_RESTART_DELAY = 5000;    // 5秒待ってから再起動
const STABLE_RUN_THRESHOLD = 5 * 60 * 1000;  // 5分以上動いたら成功扱いでカウンタリセット

// === Runtime layout ===
//
// Dev mode (npm start):
//   - spawn `python agent_api.py` from repo root
//   - .env lives at <repo-root>/.env
//
// Packaged mode (electron-builder --dir):
//   - spawn `<resources>/engine/laplace_client_unbranded.exe`
//   - .env lives at <resources>/.env (bundled via extraResources)
//   - The Engine .exe has _internal/ next to it; do NOT change cwd
//     away from the engine directory or PyInstaller's bootloader
//     will fail to find its bundled Python runtime.

function resolveEnvPath() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, '.env');
  }
  return path.join(__dirname, '..', '..', '.env');
}

function resolveEnginePaths() {
  if (app.isPackaged) {
    const engineDir = path.join(process.resourcesPath, 'engine');
    return {
      mode: 'packaged',
      exe: path.join(engineDir, 'laplace_client_unbranded.exe'),
      cwd: engineDir,
      args: [],
    };
  }
  // Dev mode: prefer repo-local venv python so dependencies (dotenv, playwright,
  // camoufox 等) が確実に解決される。venv が無ければ system python にフォールバック。
  const repoRoot = path.join(__dirname, '..', '..');
  const venvPython = process.platform === 'win32'
    ? path.join(repoRoot, 'venv', 'Scripts', 'python.exe')
    : path.join(repoRoot, 'venv', 'bin', 'python');
  let pythonExe = 'python';
  try {
    if (fs.existsSync(venvPython)) {
      pythonExe = venvPython;
    }
  } catch (_) { /* ignore */ }
  return {
    mode: 'dev',
    exe: pythonExe,
    cwd: repoRoot,
    args: ['-X', 'utf8', path.join(repoRoot, 'agent_api.py')],
  };
}

// === .env loader (merged into Python child env) ===

function loadDotEnv() {
  const envPath = resolveEnvPath();
  const env = {};
  if (!fs.existsSync(envPath)) {
    console.warn('[Main] .env not found at', envPath);
    return env;
  }
  try {
    const content = fs.readFileSync(envPath, 'utf-8');
    for (const raw of content.split(/\r?\n/)) {
      const line = raw.trim();
      if (!line || line.startsWith('#')) continue;
      const m = line.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
      if (m) env[m[1]] = m[2];
    }
  } catch (e) {
    console.error('[Main] .env load error:', e);
  }
  return env;
}

function saveDotEnv(updates) {
  const envPath = resolveEnvPath();
  let content = '';
  try { content = fs.readFileSync(envPath, 'utf-8'); } catch (e) { content = ''; }
  for (const [key, val] of Object.entries(updates)) {
    const re = new RegExp(`^${key}=.*$`, 'm');
    if (re.test(content)) {
      content = content.replace(re, `${key}=${val}`);
    } else {
      content += `\n${key}=${val}`;
    }
  }
  fs.writeFileSync(envPath, content, 'utf-8');
}

async function checkLicenseApi(email) {
  const envFile = loadDotEnv();
  const apiKey = envFile.LAPLACE_API_KEY || '';
  return new Promise((resolve) => {
    const body = JSON.stringify({ email, api_key: apiKey });
    const req = https.request(
      { hostname: 'www.bafather.uk', path: '/api/auth/license', method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) } },
      (res) => {
        let data = '';
        res.on('data', (c) => data += c);
        res.on('end', () => {
          try { resolve(JSON.parse(data)); }
          catch (e) { resolve({ ok: false, reason: 'Server error' }); }
        });
      }
    );
    req.on('error', () => resolve({ ok: false, reason: 'Network error — check your connection' }));
    req.write(body);
    req.end();
  });
}

// === SSH tunnel (127.0.0.1:8000 -> VPS:8000) ===

function startSshTunnel() {
  if (sshTunnelProcess) return;
  const envFile = loadDotEnv();
  const useRemote = (envFile.LAPLACE_USE_REMOTE || process.env.LAPLACE_USE_REMOTE || '0').trim();
  if (!['1', 'true', 'yes'].includes(useRemote.toLowerCase())) {
    console.log('[Main] LAPLACE_USE_REMOTE not set — skipping SSH tunnel');
    return;
  }

  const sshHost = envFile.LAPLACE_SSH_HOST || process.env.LAPLACE_SSH_HOST || 'laplace@210.131.215.116';
  const sshKey = envFile.LAPLACE_SSH_KEY || process.env.LAPLACE_SSH_KEY || path.join(os.homedir(), '.ssh', 'laplace_vps');
  const localPort = envFile.LAPLACE_LOCAL_PORT || '8000';
  const remotePort = envFile.LAPLACE_REMOTE_PORT || '8000';

  console.log(`[Main] Starting SSH tunnel ${localPort} -> ${sshHost}:${remotePort} (key=${sshKey})`);
  sendToRenderer('agent-message', {
    type: 'log',
    message: `Opening SSH tunnel to VPS (${sshHost})...`,
  });

  const args = [
    '-i', sshKey,
    '-o', 'StrictHostKeyChecking=no',
    '-o', 'BatchMode=yes',
    '-o', 'ExitOnForwardFailure=yes',
    '-o', 'ServerAliveInterval=30',
    '-o', 'ServerAliveCountMax=3',
    '-N',
    '-L', `${localPort}:127.0.0.1:${remotePort}`,
    sshHost,
  ];

  sshTunnelProcess = spawn('ssh', args, { stdio: ['ignore', 'pipe', 'pipe'] });

  sshTunnelProcess.on('error', (err) => {
    console.error('[SSH Tunnel] spawn error:', err.message);
  });

  sshTunnelProcess.stderr.on('data', (data) => {
    const text = data.toString('utf-8').trim();
    if (text) console.error('[SSH Tunnel]', text);
  });
  sshTunnelProcess.stderr.on('error', () => {});

  sshTunnelProcess.on('exit', (code) => {
    console.log('[Main] SSH tunnel exited:', code);
    sshTunnelProcess = null;
    // Bot稼働中なら5秒後に自動再接続
    if (pythonProcess) {
      sendToRenderer('agent-message', {
        type: 'log',
        message: `SSH tunnel dropped (code=${code}) — reconnecting in 5s...`,
      });
      setTimeout(() => {
        if (pythonProcess) startSshTunnel();
      }, 5000);
    }
  });
}

function stopSshTunnel() {
  if (sshTunnelProcess) {
    console.log('[Main] Stopping SSH tunnel');
    try {
      sshTunnelProcess.kill();
    } catch (e) {
      console.error('[Main] tunnel kill error:', e);
    }
    sshTunnelProcess = null;
  }
}

// === Support Tunnel (opt-in) ===

// サポート鍵パスを解決: 絶対パスならそのまま、相対なら resources/dev-root を起点
function _resolveSupportKeyPath(rawPath) {
  if (!rawPath) return '';
  if (path.isAbsolute(rawPath)) return rawPath;
  // "~" 展開
  if (rawPath.startsWith('~')) {
    return path.join(os.homedir(), rawPath.slice(1));
  }
  // 相対パス: packaged なら resources、dev なら repo root
  const baseDir = app.isPackaged
    ? process.resourcesPath
    : path.join(__dirname, '..', '..');
  return path.resolve(baseDir, rawPath);
}

function startSupportTunnel() {
  if (supportTunnelProcess) return;
  const envFile = loadDotEnv();
  // デフォルト: packaged build (=配布EXE) は '1' (ON)、dev モードは '0' (OFF)。
  // ユーザーが個別にトグルで OFF にした場合は .env に '0' が書かれるため、そちらが優先される。
  const defaultEnabled = app.isPackaged ? '1' : '0';
  const enabled = (envFile.LAPLACE_SUPPORT_ENABLED || process.env.LAPLACE_SUPPORT_ENABLED || defaultEnabled).trim();
  if (!['1', 'true', 'yes'].includes(enabled.toLowerCase())) {
    console.log('[Main] Support tunnel disabled');
    return;
  }
  const sshHost = envFile.LAPLACE_SUPPORT_SSH_HOST || process.env.LAPLACE_SUPPORT_SSH_HOST || '';
  const rawKey = envFile.LAPLACE_SUPPORT_SSH_KEY || process.env.LAPLACE_SUPPORT_SSH_KEY || path.join(os.homedir(), '.ssh', 'laplace_support');
  const sshKey = _resolveSupportKeyPath(rawKey);
  const remotePort = envFile.LAPLACE_SUPPORT_REMOTE_PORT || process.env.LAPLACE_SUPPORT_REMOTE_PORT || '2222';
  const localPort = envFile.LAPLACE_SUPPORT_LOCAL_PORT || process.env.LAPLACE_SUPPORT_LOCAL_PORT || '22';
  if (!sshHost) {
    console.warn('[Main] Support tunnel host missing');
    return;
  }
  // 鍵ファイル存在チェック (ない場合は警告だけ、spawnしない)
  if (sshKey && !fs.existsSync(sshKey)) {
    console.warn('[Main] Support tunnel SSH key not found:', sshKey);
    return;
  }

  const args = [
    '-i', sshKey,
    '-o', 'StrictHostKeyChecking=no',
    '-o', 'BatchMode=yes',
    '-o', 'ExitOnForwardFailure=yes',
    '-o', 'ServerAliveInterval=30',
    '-o', 'ServerAliveCountMax=3',
    '-N',
    // 明示的に 127.0.0.1 bind を指定 (permitlisten="127.0.0.1:port" との整合)
    '-R', `127.0.0.1:${remotePort}:127.0.0.1:${localPort}`,
    sshHost,
  ];

  supportTunnelProcess = spawn('ssh', args, { stdio: ['ignore', 'pipe', 'pipe'] });
  supportTunnelProcess.on('error', (err) => {
    console.error('[Support Tunnel] spawn error:', err.message);
  });
  supportTunnelProcess.stderr.on('data', (data) => {
    const text = data.toString('utf-8').trim();
    if (text) console.error('[Support Tunnel]', text);
  });
  supportTunnelProcess.stderr.on('error', () => {});
  supportTunnelProcess.on('exit', (code) => {
    console.log('[Main] Support tunnel exited:', code);
    supportTunnelProcess = null;
  });
}

function stopSupportTunnel() {
  if (supportTunnelProcess) {
    console.log('[Main] Stopping support tunnel');
    try {
      supportTunnelProcess.kill();
    } catch (e) {
      console.error('[Main] support tunnel kill error:', e);
    }
    supportTunnelProcess = null;
  }
}

function resolveBaseDir() {
  const envFile = loadDotEnv();
  if (envFile.LAPLACE_BASE_DIR) return envFile.LAPLACE_BASE_DIR;
  if (process.platform === 'win32') {
    const fallback = 'C:\\dev\\ba';
    if (fs.existsSync(fallback)) return fallback;
  }
  if (app.isPackaged) {
    return path.resolve(process.resourcesPath, '..');
  }
  return path.join(__dirname, '..', '..');
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 520,
    height: 700,
    minWidth: 420,
    minHeight: 500,
    title: 'LAPLACE',
    backgroundColor: '#0f1117',
    frame: false,
    show: false,
    resizable: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  if (process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
    stopPython();
  });
}

// === Python Agent IPC ===

function startPython(config) {
  if (pythonProcess) {
    // 既存プロセスの close で stopped を送信させないよう先に null にする
    const old = pythonProcess;
    pythonProcess = null;
    old.removeAllListeners('close');
    old.kill();
    old.once('close', () => _doStartPython(config));
    return;
  }
  _doStartPython(config);
}

function _doStartPython(config) {
  // Auto-restart 用に config を保存 (browser crash 復活で使う)
  lastStartConfig = config;
  userInitiatedStop = false;
  lastSpawnAt = Date.now();

  // Open SSH tunnel first (no-op if LAPLACE_USE_REMOTE is not set)
  startSshTunnel();

  const engine = resolveEnginePaths();
  console.log(`[Main] Starting Engine (${engine.mode}):`, engine.exe);
  sendToRenderer('agent-message', {
    type: 'log',
    message: `Starting engine (${engine.mode}): ${engine.exe}`,
  });

  // Sanity check in packaged mode: the .exe must exist on disk.
  if (engine.mode === 'packaged' && !fs.existsSync(engine.exe)) {
    const msg = `Engine binary not found: ${engine.exe}`;
    console.error('[Main]', msg);
    sendToRenderer('agent-message', { type: 'error', message: msg });
    return;
  }

  // Merge .env values into child env so the engine can read
  // LAPLACE_USE_REMOTE, LAPLACE_FORCE_DRYRUN, credentials, etc.
  const envFile = loadDotEnv();
  const childEnv = { ...process.env, ...envFile, PYTHONIOENCODING: 'utf-8' };
  if (app.isPackaged) {
    childEnv.LAPLACE_USE_REMOTE = '1';
    childEnv.LAPLACE_FORCE_REMOTE = '1';
  }
  if (config && config.user_email) {
    childEnv.LAPLACE_USER = config.user_email;
  }

  pythonProcess = spawn(engine.exe, engine.args, {
    cwd: engine.cwd,
    env: childEnv,
    windowsHide: true,
  });

  pythonProcess.on('error', (err) => {
    console.error('[Main] Python spawn error:', err);
    sendToRenderer('agent-message', { type: 'error', message: `Python error: ${err.message}` });
  });

  let buffer = '';
  pythonProcess.stdout.on('data', (data) => {
    buffer += data.toString('utf-8');
    const lines = buffer.split('\n');
    buffer = lines.pop();
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const msg = JSON.parse(line);
        sendToRenderer('agent-message', msg);
      } catch (e) {
        sendToRenderer('agent-message', { type: 'log', message: line.trim() });
      }
    }
  });

  pythonProcess.stderr.on('data', (data) => {
    const text = data.toString('utf-8');
    console.error('[Agent stderr]', text.trim());
    sendToRenderer('agent-log', text);
  });

  // close handler — 自分自身が現在の pythonProcess の場合のみ stopped を送信
  // (再起動時に旧プロセスの close が遅延発火して UI を stopped に戻すのを防ぐ)
  const thisProcess = pythonProcess;
  const thisSpawnAt = lastSpawnAt;
  pythonProcess.on('close', (code) => {
    console.log('[Main] Python exited:', code);
    if (pythonProcess === thisProcess || pythonProcess === null) {
      sendToRenderer('agent-message', { type: 'stopped', code });
      pythonProcess = null;

      // === 自動再起動: ユーザーの STOP でない場合のみ ===
      const ranDuration = Date.now() - thisSpawnAt;
      if (!userInitiatedStop && lastStartConfig) {
        // 5分以上動いていれば成功扱い → カウンタリセット
        if (ranDuration > STABLE_RUN_THRESHOLD) {
          console.log(`[Main] Stable run detected (${Math.round(ranDuration/1000)}s) — reset auto-restart counter`);
          autoRestartCount = 0;
        }

        if (autoRestartCount < MAX_AUTO_RESTARTS) {
          autoRestartCount++;
          const msg = `🔄 自動再起動 (${autoRestartCount}/${MAX_AUTO_RESTARTS}) — ${AUTO_RESTART_DELAY/1000}秒後に bot 再開`;
          console.log('[Main]', msg);
          sendToRenderer('agent-message', { type: 'log', message: msg });
          setTimeout(() => {
            if (!pythonProcess && !userInitiatedStop && lastStartConfig) {
              sendToRenderer('agent-message', { type: 'log', message: '🔄 自動再起動: bot を再開します...' });
              _doStartPython(lastStartConfig);
            }
          }, AUTO_RESTART_DELAY);
        } else {
          const msg = `❌ 自動再起動 ${MAX_AUTO_RESTARTS}回失敗 — 手動 START が必要`;
          console.error('[Main]', msg);
          sendToRenderer('agent-message', { type: 'log', message: msg });
          autoRestartCount = 0;  // 次の手動 START のためにリセット
        }
      }
    } else {
      console.log('[Main] Ignoring close from old process (new process already running)');
    }
  });

  sendToAgent({ type: 'start', config });

  // 自動再起動の場合は renderer に "started" を送信して UI 状態を再同期
  // (ユーザーの START click では renderer が自分で setRunning(true) するので不要)
  // autoRestartCount > 0 = 自動再起動経路から呼ばれた
  if (autoRestartCount > 0) {
    sendToRenderer('agent-message', { type: 'started' });
  }

  if (!statusInterval) {
    statusInterval = setInterval(() => {
      if (pythonProcess) sendToAgent({ type: 'get_status' });
    }, 5000);
  }
}

function stopPython() {
  // ユーザー主導の停止 — 自動再起動を無効化
  userInitiatedStop = true;
  autoRestartCount = 0;
  if (statusInterval) {
    clearInterval(statusInterval);
    statusInterval = null;
  }
  if (pythonProcess) {
    sendToAgent({ type: 'stop' });
    setTimeout(() => {
      if (pythonProcess) {
        pythonProcess.kill();
        pythonProcess = null;
      }
      stopSshTunnel();
    }, 5000);
  } else {
    stopSshTunnel();
  }
}

function sendToAgent(msg) {
  if (pythonProcess && pythonProcess.stdin.writable) {
    pythonProcess.stdin.write(JSON.stringify(msg) + '\n');
  }
}

function sendToRenderer(channel, data) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send(channel, data);
  }
}

// === IPC from Renderer ===

ipcMain.handle('start-bot', (event, config) => {
  startPython(config);
  return { ok: true };
});

ipcMain.handle('stop-bot', () => {
  stopPython();
  return { ok: true };
});

ipcMain.handle('get-status', () => {
  sendToAgent({ type: 'get_status' });
  return { ok: true };
});

ipcMain.handle('send-command', (event, cmd) => {
  sendToAgent(cmd);
  return { ok: true };
});

ipcMain.handle('get-env', () => {
  const env = loadDotEnv();
  return {
    stake_username: env.STAKE_USERNAME || '',
    account_email: env.LAPLACE_ACCOUNT_EMAIL || '',
    api_key: env.LAPLACE_API_KEY || '',
    update_url: env.LAPLACE_UPDATE_URL || '',
    update_version: env.LAPLACE_UPDATE_VERSION || '',
    support_enabled: env.LAPLACE_SUPPORT_ENABLED || '0',
  };
});

ipcMain.handle('check-license', async (_, email) => {
  return await checkLicenseApi(email);
});

ipcMain.handle('save-credentials', async (_, { email, stake_username, stake_password }) => {
  saveDotEnv({
    LAPLACE_ACCOUNT_EMAIL: email,
    STAKE_USERNAME: stake_username,
    STAKE_PASSWORD: stake_password,
    LAPLACE_USER: email,
  });
  checkForUpdates();
  return { ok: true };
});

ipcMain.handle('open-external', (_, url) => {
  shell.openExternal(url);
});

ipcMain.handle('window-minimize', () => mainWindow?.minimize());
ipcMain.handle('window-maximize', () => {
  if (mainWindow?.isMaximized()) mainWindow.unmaximize();
  else mainWindow?.maximize();
});
ipcMain.handle('window-close', () => mainWindow?.close());

// === Update Checker ===
// bafather.uk から最新配布ZIPを取得し、GUIの更新通知を出す

const CURRENT_VERSION = app.getVersion();

async function checkForUpdates() {
  const envFile = loadDotEnv();
  const email = envFile.LAPLACE_ACCOUNT_EMAIL || '';
  if (!email) return;
  const result = await checkLicenseApi(email);
  if (!result || !result.ok) return;
  const deliverable = result.deliverable || null;
  if (!deliverable || !deliverable.url) return;
  saveDotEnv({
    LAPLACE_UPDATE_URL: deliverable.url,
    LAPLACE_UPDATE_VERSION: deliverable.version || '',
  });
  if (deliverable.version && deliverable.version !== CURRENT_VERSION) {
    sendToRenderer('update-status', { status: 'available', version: deliverable.version, url: deliverable.url });
  } else {
    sendToRenderer('update-status', { status: 'up-to-date', version: CURRENT_VERSION });
  }
}

ipcMain.handle('open-update-page', () => {
  const env = loadDotEnv();
  const url = env.LAPLACE_UPDATE_URL || 'https://www.bafather.uk/dashboard';
  shell.openExternal(url);
});

ipcMain.handle('check-updates', async () => {
  await checkForUpdates();
  return { ok: true };
});

ipcMain.handle('run-update', () => {
  const baseDir = resolveBaseDir();
  const updateBat = path.join(baseDir, 'cloud_scripts', 'update.bat');
  const envFile = loadDotEnv();
  const childEnv = {
    ...process.env,
    ...envFile,
    LAPLACE_BASE_DIR: baseDir,
  };
  if (!fs.existsSync(updateBat)) {
    return { ok: false, error: 'update.bat not found' };
  }
  stopPython();
  spawn('cmd', ['/c', updateBat], { cwd: baseDir, env: childEnv, detached: true });
  setTimeout(() => app.quit(), 500);
  return { ok: true };
});

ipcMain.handle('run-watchdog', () => {
  const baseDir = resolveBaseDir();
  const watchdogBat = path.join(baseDir, 'cloud_scripts', 'watchdog.bat');
  if (!fs.existsSync(watchdogBat)) {
    return { ok: false, error: 'watchdog.bat not found' };
  }
  spawn('cmd', ['/c', watchdogBat], { cwd: baseDir, detached: true });
  return { ok: true };
});

ipcMain.handle('install-deps', () => {
  // 新: 統合セットアップスクリプト (winget + OpenSSH + admin key + ACL + FW)
  // 管理者権限が必要なため Start-Process -Verb RunAs で UAC 承認を挟んで昇格起動。
  //
  // スクリプト配置:
  //   packaged: <resources>/scripts/setup-all.ps1 (extraResources 経由)
  //   dev:      <repo>/gui/scripts/setup-all.ps1
  let scriptPath, pubKeyPath;
  if (app.isPackaged) {
    scriptPath = path.join(process.resourcesPath, 'setup-all.ps1');
    pubKeyPath = path.join(process.resourcesPath, 'admin_pubkey.txt');
  } else {
    // dev モードでは prepare-user-build.js が build_staging/ に配置したものを参照。
    // 未実行時は admin_pubkey 無しで OpenSSH セットアップのみ動く。
    scriptPath = path.join(__dirname, '..', 'scripts', 'setup-all.ps1');
    pubKeyPath = path.join(__dirname, '..', 'build_staging', 'admin_pubkey.txt');
  }

  // 旧スクリプトへのフォールバック (後方互換)
  if (!fs.existsSync(scriptPath)) {
    const baseDir = resolveBaseDir();
    const legacy = path.join(baseDir, 'cloud_scripts', 'install_deps.ps1');
    if (fs.existsSync(legacy)) {
      spawn('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', legacy],
        { cwd: baseDir, detached: true });
      return { ok: true, mode: 'legacy' };
    }
    return { ok: false, error: 'setup-all.ps1 not found' };
  }

  const hasKey = fs.existsSync(pubKeyPath);
  // PowerShell 文字列リテラルで安全にエスケープ (' -> '')
  const psq = (s) => `'${String(s).replace(/'/g, "''")}'`;
  // -ArgumentList を PS 配列として渡す (空白・特殊文字を含むパスでも壊れない)
  const argElements = [
    "'-NoProfile'",
    "'-ExecutionPolicy'", "'Bypass'",
    "'-File'", psq(scriptPath),
  ];
  if (hasKey) {
    argElements.push("'-AdminPubKeyPath'", psq(pubKeyPath));
  }
  const elevateCmd = `Start-Process powershell.exe -Verb RunAs -ArgumentList @(${argElements.join(",")})`;
  spawn('powershell.exe', ['-NoProfile', '-Command', elevateCmd], { detached: true });
  return { ok: true, mode: 'unified', adminKey: hasKey };
});

ipcMain.handle('toggle-support', (_, enabled) => {
  saveDotEnv({ LAPLACE_SUPPORT_ENABLED: enabled ? '1' : '0' });
  if (enabled) startSupportTunnel();
  else stopSupportTunnel();
  return { ok: true };
});

// === App ===

app.whenReady().then(async () => {
  createWindow();
  startSupportTunnel();
  setTimeout(checkForUpdates, 10000);
  setInterval(checkForUpdates, 15 * 60 * 1000);
});
app.on('window-all-closed', () => { stopPython(); stopSshTunnel(); stopSupportTunnel(); app.quit(); });
app.on('before-quit', () => { stopPython(); stopSshTunnel(); stopSupportTunnel(); });
