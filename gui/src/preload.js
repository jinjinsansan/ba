const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('valhalla', {
  startBot: (config) => ipcRenderer.invoke('start-bot', config),
  stopBot: () => ipcRenderer.invoke('stop-bot'),
  sendCommand: (cmd) => ipcRenderer.invoke('send-command', cmd),
  getStatus: () => ipcRenderer.invoke('get-status'),

  onAgentMessage: (cb) => ipcRenderer.on('agent-message', (_, msg) => cb(msg)),
  onAgentLog: (cb) => ipcRenderer.on('agent-log', (_, text) => cb(text)),

  windowMinimize: () => ipcRenderer.invoke('window-minimize'),
  windowMaximize: () => ipcRenderer.invoke('window-maximize'),
  windowClose: () => ipcRenderer.invoke('window-close'),

  getEnv: () => ipcRenderer.invoke('get-env'),

  onUpdateStatus: (cb) => ipcRenderer.on('update-status', (_, data) => cb(data)),
  openUpdatePage: () => ipcRenderer.invoke('open-update-page'),
});
