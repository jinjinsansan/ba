const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow = null;
let pythonProcess = null;
let statusInterval = null;

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

  const agentPath = path.join(__dirname, '..', '..', 'agent_api.py');
  console.log('[Main] Starting Python agent:', agentPath);
  sendToRenderer('agent-message', { type: 'log', message: `Starting agent: ${agentPath}` });

  pythonProcess = spawn('python', ['-X', 'utf8', agentPath], {
    cwd: path.join(__dirname, '..', '..'),
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
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
    }, 5000);
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
app.on('window-all-closed', () => { stopPython(); app.quit(); });
app.on('before-quit', () => stopPython());
