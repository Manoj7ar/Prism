import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electron', {
  executeCommand: (command: string) => ipcRenderer.invoke('execute-command', command),
  getContext: () => ipcRenderer.invoke('get-context'),
  onStartRecording: (callback: () => void) => ipcRenderer.on('start-recording', callback),
  onToggleRecording: (callback: () => void) => {
    ipcRenderer.removeAllListeners('toggle-recording');
    ipcRenderer.on('toggle-recording', () => callback());
  },
  showSummary: (content: string) => ipcRenderer.invoke('show-summary', content),
  onUpdateSummary: (callback: (content: string) => void) => {
    ipcRenderer.removeAllListeners('update-summary');
    ipcRenderer.on('update-summary', (event, content) => callback(content));
  },
  resizeWindow: (width: number, height: number) => ipcRenderer.invoke('resize-window', width, height),
  stopExecution: () => ipcRenderer.invoke('stop-execution'),
  getTasks: () => ipcRenderer.invoke('get-tasks'),
    onWindowShow: (callback: (data?: { activeApp: string }) => void) => {
      ipcRenderer.removeAllListeners('window-show');
      ipcRenderer.on('window-show', (_event, data) => callback(data));
    },
    onWindowHide: (callback: () => void) => {
      ipcRenderer.removeAllListeners('window-hide');
      ipcRenderer.on('window-hide', () => callback());
    },
    hideWindow: () => ipcRenderer.invoke('hide-window'),
    getMemoryStatus: () => ipcRenderer.invoke('get-memory-status'),
    clearMemory: () => ipcRenderer.invoke('clear-memory'),
    getPresets: () => ipcRenderer.invoke('get-presets'),
    savePreset: (preset: any) => ipcRenderer.invoke('save-preset', preset),
      deletePreset: (presetId: string) => ipcRenderer.invoke('delete-preset', presetId),
      executePreset: (steps: string[], history: any[]) => ipcRenderer.invoke('execute-preset', steps, history),
      setApiKey: (key: string) => ipcRenderer.invoke('set-api-key', key),
      getApiKey: () => ipcRenderer.invoke('get-api-key'),
      showAutomationOverlay: (show: boolean) => ipcRenderer.invoke('show-automation-overlay', show),
    });




