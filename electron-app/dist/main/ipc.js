"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.setupIpcHandlers = setupIpcHandlers;
const electron_1 = require("electron");
const main_1 = require("./main");
const overlay_1 = require("./overlay");
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
const electron_store_1 = __importDefault(require("electron-store"));
const store = new electron_store_1.default();
const PRESETS_FILE = path_1.default.join(electron_1.app.getPath('userData'), 'presets.json');
function ensurePresetsFile() {
    if (!fs_1.default.existsSync(PRESETS_FILE)) {
        fs_1.default.writeFileSync(PRESETS_FILE, JSON.stringify([]));
    }
}
function setupIpcHandlers() {
    ensurePresetsFile();
    electron_1.ipcMain.handle('get-presets', async () => {
        try {
            ensurePresetsFile();
            const data = fs_1.default.readFileSync(PRESETS_FILE, 'utf8');
            return JSON.parse(data);
        }
        catch (error) {
            // console.error('Failed to get presets:', error);
            return [];
        }
    });
    electron_1.ipcMain.handle('save-preset', async (event, preset) => {
        try {
            ensurePresetsFile();
            const data = fs_1.default.readFileSync(PRESETS_FILE, 'utf8');
            let presets = JSON.parse(data);
            const index = presets.findIndex((p) => p.id === preset.id);
            if (index >= 0) {
                presets[index] = preset;
            }
            else {
                presets.push(preset);
            }
            fs_1.default.writeFileSync(PRESETS_FILE, JSON.stringify(presets, null, 2));
            return { success: true };
        }
        catch (error) {
            // console.error('Failed to save preset:', error);
            return { success: false, error: error.message };
        }
    });
    electron_1.ipcMain.handle('delete-preset', async (event, presetId) => {
        try {
            ensurePresetsFile();
            const data = fs_1.default.readFileSync(PRESETS_FILE, 'utf8');
            let presets = JSON.parse(data);
            presets = presets.filter((p) => p.id !== presetId);
            fs_1.default.writeFileSync(PRESETS_FILE, JSON.stringify(presets, null, 2));
            return { success: true };
        }
        catch (error) {
            // console.error('Failed to delete preset:', error);
            return { success: false, error: error.message };
        }
    });
    electron_1.ipcMain.handle('execute-command', async (event, command) => {
        try {
            const params = new URLSearchParams();
            params.append('command', command);
            const response = await electron_1.net.fetch('http://localhost:8000/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: params.toString()
            });
            return await response.json();
        }
        catch (error) {
            return { success: false, error: error.message };
        }
    });
    electron_1.ipcMain.handle('execute-preset', async (event, steps, history) => {
        try {
            const response = await electron_1.net.fetch('http://localhost:8000/execute-preset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ steps, history })
            });
            return await response.json();
        }
        catch (error) {
            return { success: false, error: error.message };
        }
    });
    electron_1.ipcMain.handle('stop-execution', async () => {
        try {
            const response = await electron_1.net.fetch('http://localhost:8000/stop', {
                method: 'POST'
            });
            return await response.json();
        }
        catch (error) {
            return { success: false, error: error.message };
        }
    });
    electron_1.ipcMain.handle('get-context', async () => {
        try {
            const response = await electron_1.net.fetch('http://localhost:8000/context');
            return await response.json();
        }
        catch (error) {
            return { success: false, error: error.message };
        }
    });
    electron_1.ipcMain.handle('show-summary', async (event, content) => {
        (0, main_1.createSummaryWindow)(content);
        return { success: true };
    });
    electron_1.ipcMain.handle('resize-window', (event, width, height) => {
        const win = electron_1.BrowserWindow.fromWebContents(event.sender);
        if (win) {
            const { screen } = require('electron');
            const cursorPoint = screen.getCursorScreenPoint();
            const activeDisplay = screen.getDisplayNearestPoint(cursorPoint);
            const { width: screenWidth, height: screenHeight, x: screenX, y: screenY } = activeDisplay.workArea;
            const targetX = screenX + Math.round((screenWidth - width) / 2);
            const targetY = screenY + screenHeight - height - 10;
            const currentBounds = win.getBounds();
            const startHeight = currentBounds.height;
            const startY = currentBounds.y;
            const deltaHeight = height - startHeight;
            const deltaY = targetY - startY;
            // Skip animation for small changes
            if (Math.abs(deltaHeight) < 20) {
                win.setBounds({ width, height, x: targetX, y: targetY });
                return { success: true };
            }
            const steps = 16;
            const interval = 18; // ~280ms total
            let step = 0;
            const timer = setInterval(() => {
                step++;
                // Ease-out cubic: 1 - (1 - t)^3
                const t = step / steps;
                const ease = 1 - Math.pow(1 - t, 3);
                const currentH = Math.round(startHeight + deltaHeight * ease);
                const currentY = Math.round(startY + deltaY * ease);
                win.setBounds({ width, height: currentH, x: targetX, y: currentY });
                if (step >= steps) {
                    clearInterval(timer);
                    win.setBounds({ width, height, x: targetX, y: targetY });
                }
            }, interval);
        }
        return { success: true };
    });
    electron_1.ipcMain.handle('get-tasks', async () => {
        try {
            const response = await electron_1.net.fetch('http://localhost:8000/tasks');
            return await response.json();
        }
        catch (error) {
            return { success: false, error: error.message };
        }
    });
    electron_1.ipcMain.handle('hide-window', (event) => {
        const win = electron_1.BrowserWindow.fromWebContents(event.sender);
        if (win) {
            win.hide();
        }
        return { success: true };
    });
    electron_1.ipcMain.handle('get-memory-status', async () => {
        try {
            const response = await electron_1.net.fetch('http://localhost:8000/memory-status');
            return await response.json();
        }
        catch (error) {
            return { success: false, error: error.message };
        }
    });
    electron_1.ipcMain.handle('clear-memory', async () => {
        try {
            const response = await electron_1.net.fetch('http://localhost:8000/memory-clear', {
                method: 'POST'
            });
            return await response.json();
        }
        catch (error) {
            return { success: false, error: error.message };
        }
    });
    electron_1.ipcMain.handle('set-api-key', async (event, key) => {
        try {
            store.set('GEMINI_API_KEY', key);
            // Also update backend if it's running
            try {
                await electron_1.net.fetch('http://localhost:8000/set-key', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key })
                });
            }
            catch (e) { }
            return { success: true };
        }
        catch (error) {
            return { success: false, error: error.message };
        }
    });
    electron_1.ipcMain.handle('get-api-key', async () => {
        return store.get('GEMINI_API_KEY') || '';
    });
    electron_1.ipcMain.handle('show-automation-overlay', async (event, show) => {
        if (show) {
            (0, overlay_1.showOverlay)();
        }
        else {
            (0, overlay_1.hideOverlay)();
        }
        return { success: true };
    });
}
