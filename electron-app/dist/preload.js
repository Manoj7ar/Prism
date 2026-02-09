"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
electron_1.contextBridge.exposeInMainWorld('electron', {
    executeCommand: (command) => electron_1.ipcRenderer.invoke('execute-command', command),
    getContext: () => electron_1.ipcRenderer.invoke('get-context'),
    onStartRecording: (callback) => electron_1.ipcRenderer.on('start-recording', callback),
    onToggleRecording: (callback) => {
        electron_1.ipcRenderer.removeAllListeners('toggle-recording');
        electron_1.ipcRenderer.on('toggle-recording', () => callback());
    },
    showSummary: (content) => electron_1.ipcRenderer.invoke('show-summary', content),
    onUpdateSummary: (callback) => {
        electron_1.ipcRenderer.removeAllListeners('update-summary');
        electron_1.ipcRenderer.on('update-summary', (event, content) => callback(content));
    },
    resizeWindow: (width, height) => electron_1.ipcRenderer.invoke('resize-window', width, height),
    stopExecution: () => electron_1.ipcRenderer.invoke('stop-execution'),
    getTasks: () => electron_1.ipcRenderer.invoke('get-tasks'),
    onWindowShow: (callback) => {
        electron_1.ipcRenderer.removeAllListeners('window-show');
        electron_1.ipcRenderer.on('window-show', (_event, data) => callback(data));
    },
    onWindowHide: (callback) => {
        electron_1.ipcRenderer.removeAllListeners('window-hide');
        electron_1.ipcRenderer.on('window-hide', () => callback());
    },
    hideWindow: () => electron_1.ipcRenderer.invoke('hide-window'),
    getMemoryStatus: () => electron_1.ipcRenderer.invoke('get-memory-status'),
    clearMemory: () => electron_1.ipcRenderer.invoke('clear-memory'),
    getPresets: () => electron_1.ipcRenderer.invoke('get-presets'),
    savePreset: (preset) => electron_1.ipcRenderer.invoke('save-preset', preset),
    deletePreset: (presetId) => electron_1.ipcRenderer.invoke('delete-preset', presetId),
    executePreset: (steps, history) => electron_1.ipcRenderer.invoke('execute-preset', steps, history),
    setApiKey: (key) => electron_1.ipcRenderer.invoke('set-api-key', key),
    getApiKey: () => electron_1.ipcRenderer.invoke('get-api-key'),
    showAutomationOverlay: (show) => electron_1.ipcRenderer.invoke('show-automation-overlay', show),
});
