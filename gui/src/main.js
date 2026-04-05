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

let mainWindow = null;
let pythonProcess = null;
let sshTunnelProcess = null;
let statusInterval = null;

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
  return {
    mode: 'dev',
    exe: 'python',
    cwd: path.join(__dirname, '..', '..'),
    args: ['-X', 'utf8', path.join(__dirname, '..', '..', 'agent_api.py')],
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

  sshTunnelProcess.stderr.on('data', (data) => {
    const text = data.toString('utf-8').trim();
    if (text) console.error('[SSH Tunnel]', text);
  });

  sshTunnelProcess.on('exit', (code) => {
    console.log('[Main] SSH tunnel exited:', code);
    sshTunnelProcess = null;
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
    pythonProcess.kill();
  }

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

  pythonProcess.on('close', (code) => {
    console.log('[Main] Python exited:', code);
    sendToRenderer('agent-message', { type: 'stopped', code });
    pythonProcess = null;
  });

  sendToAgent({ type: 'start', config });

  if (!statusInterval) {
    statusInterval = setInterval(() => {
      if (pythonProcess) sendToAgent({ type: 'get_status' });
    }, 5000);
  }
}

function stopPython() {
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

ipcMain.handle('window-minimize', () => mainWindow?.minimize());
ipcMain.handle('window-maximize', () => {
  if (mainWindow?.isMaximized()) mainWindow.unmaximize();
  else mainWindow?.maximize();
});
ipcMain.handle('window-close', () => mainWindow?.close());

// === App ===

app.whenReady().then(createWindow);
app.on('window-all-closed', () => { stopPython(); stopSshTunnel(); app.quit(); });
app.on('before-quit', () => { stopPython(); stopSshTunnel(); });
