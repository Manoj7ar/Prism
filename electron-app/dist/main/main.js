"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createSummaryWindow = createSummaryWindow;
const electron_1 = require("electron");
const path_1 = __importDefault(require("path"));
const tray_1 = require("./tray");
const ipc_1 = require("./ipc");
const child_process_1 = require("child_process");
const electron_store_1 = __importDefault(require("electron-store"));
const overlay_1 = require("./overlay");
const store = new electron_store_1.default();
// Disable Electron security warnings
process.env.ELECTRON_DISABLE_SECURITY_WARNINGS = 'true';
let mainWindow = null;
let summaryWindow = null;
let pythonProcess = null;
let isQuitting = false;
if (!electron_1.app.isPackaged) {
    // Use isolated userData during development to avoid profile lock/encryption issues.
    electron_1.app.setPath('userData', path_1.default.join(electron_1.app.getPath('appData'), 'PrismDev'));
}
async function stopPythonExecution() {
    try {
        await electron_1.net.fetch('http://localhost:8000/stop', { method: 'POST' });
    }
    catch (err) { }
}
async function updateBackendVisibility(visible) {
    try {
        await electron_1.net.fetch('http://localhost:8000/visibility', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ visible })
        });
    }
    catch (err) { }
}
function createSummaryWindow(content) {
    if (summaryWindow) {
        summaryWindow.focus();
        summaryWindow.webContents.send('update-summary', content);
        return;
    }
    summaryWindow = new electron_1.BrowserWindow({
        width: 600,
        height: 500,
        webPreferences: {
            preload: path_1.default.join(__dirname, '../preload.js'),
            contextIsolation: true,
            nodeIntegration: false
        },
        title: 'Page Summary - Prism',
        backgroundColor: '#0f172a',
    });
    summaryWindow.loadFile(path_1.default.join(__dirname, '../renderer/index.html'), { query: { mode: 'summary' } });
    summaryWindow.webContents.on('did-finish-load', () => {
        setTimeout(() => {
            summaryWindow?.webContents.send('update-summary', content);
        }, 500);
    });
    summaryWindow.on('closed', () => {
        summaryWindow = null;
    });
}
async function waitForBackend(maxAttempts = 30) {
    for (let i = 0; i < maxAttempts; i++) {
        try {
            const response = await electron_1.net.fetch('http://localhost:8000/health');
            if (response.ok) {
                return true;
            }
        }
        catch (e) {
            // Backend not ready yet
        }
        await new Promise(r => setTimeout(r, 500));
    }
    return false;
}
function resolvePythonExecutable() {
    const fromEnv = process.env.PRISM_PYTHON_PATH;
    if (fromEnv && fs_1.default.existsSync(fromEnv)) {
        return fromEnv;
    }
    const local311 = path_1.default.join(process.env.USERPROFILE || '', 'AppData', 'Local', 'Programs', 'Python', 'Python311', 'python.exe');
    if (local311 && fs_1.default.existsSync(local311)) {
        return local311;
    }
    return 'python';
}
async function startPythonBackend() {
    const isPackaged = electron_1.app.isPackaged;
    // First check if backend is already running (external dev server)
    try {
        const response = await electron_1.net.fetch('http://localhost:8000/health');
        if (response.ok) {
            return true;
        }
    }
    catch (e) { }
    let pythonExecutable;
    let args = [];
    let cwd;
    if (isPackaged) {
        // Production: use the bundled executable
        const backendDir = path_1.default.join(process.resourcesPath, 'backend');
        pythonExecutable = path_1.default.join(backendDir, process.platform === 'win32' ? 'api.exe' : 'api');
        cwd = backendDir;
        args = []; // The frozen executable doesn't need script path args
    }
    else {
        // Development: use python and the script
        pythonExecutable = resolvePythonExecutable();
        const scriptPath = path_1.default.join(__dirname, '../../../python-backend/main.py');
        cwd = path_1.default.join(__dirname, '../../../python-backend');
        args = ['-u', scriptPath];
    }
    pythonProcess = (0, child_process_1.spawn)(pythonExecutable, args, {
        cwd,
        env: {
            ...process.env,
            GEMINI_API_KEY: store.get('GEMINI_API_KEY') || process.env.GEMINI_API_KEY || ''
        },
        stdio: ['ignore', 'pipe', 'pipe']
    });
    pythonProcess.stdout?.on('data', () => { });
    pythonProcess.stderr?.on('data', () => { });
    pythonProcess.on('error', () => { });
    pythonProcess.on('exit', () => { pythonProcess = null; });
    // Wait for backend to be ready
    return await waitForBackend();
}
function createWindow() {
    const primaryDisplay = electron_1.screen.getPrimaryDisplay();
    const { width: screenWidth, height: screenHeight, x: screenX, y: screenY } = primaryDisplay.workArea;
    const windowWidth = 520;
    const windowHeight = 250;
    const yPos = screenY + screenHeight - windowHeight - 10;
    const iconExt = process.platform === 'win32' ? 'ico' : 'png';
    const iconPath = !electron_1.app.isPackaged
        ? path_1.default.join(__dirname, `../../assets/icon.${iconExt}`)
        : path_1.default.join(process.resourcesPath, `assets/icon.${iconExt}`);
    mainWindow = new electron_1.BrowserWindow({
        width: windowWidth,
        height: windowHeight,
        x: screenX + Math.round((screenWidth - windowWidth) / 2),
        y: yPos,
        icon: iconPath,
        webPreferences: {
            preload: path_1.default.join(__dirname, '../preload.js'),
            contextIsolation: true,
            nodeIntegration: false
        },
        frame: false,
        transparent: true,
        backgroundColor: '#00000000',
        alwaysOnTop: true,
        resizable: false,
        movable: false,
        skipTaskbar: true,
        show: false,
    });
    mainWindow.loadFile(path_1.default.join(__dirname, '../renderer/index.html'));
    mainWindow.on('close', (event) => {
        if (!isQuitting) {
            event.preventDefault();
            stopPythonExecution();
            mainWindow?.hide();
        }
    });
    mainWindow.webContents.on('did-finish-load', () => {
    });
}
electron_1.app.whenReady().then(async () => {
    startPythonBackend().catch(() => { });
    createWindow();
    (0, tray_1.createTray)(mainWindow);
    (0, ipc_1.setupIpcHandlers)();
    (0, overlay_1.createOverlayWindow)();
    let isToggling = false;
    const toggleWindow = async () => {
        if (isToggling)
            return;
        isToggling = true;
        if (!mainWindow) {
            // console.error('Main: mainWindow is NULL');
            isToggling = false;
            return;
        }
        try {
            const isVisible = mainWindow.isVisible();
            if (isVisible) {
                updateBackendVisibility(false);
                mainWindow.webContents.send('window-hide');
                setTimeout(() => {
                    mainWindow?.hide();
                    isToggling = false;
                }, 350);
            }
            else {
                updateBackendVisibility(true);
                const cursorPoint = electron_1.screen.getCursorScreenPoint();
                const activeDisplay = electron_1.screen.getDisplayNearestPoint(cursorPoint);
                const { width: sw, height: sh, x: sx, y: sy } = activeDisplay.workArea;
                const { width: ww, height: wh } = mainWindow.getBounds();
                const newX = sx + Math.round((sw - ww) / 2);
                const newY = sy + sh - wh - 10;
                mainWindow.setPosition(newX, newY);
                mainWindow.show();
                mainWindow.focus();
                isToggling = false;
                mainWindow.webContents.send('window-show', { activeApp: 'Desktop' });
                electron_1.net.fetch('http://localhost:8000/active-app')
                    .then(res => res.json())
                    .then(data => {
                    if (data.success && mainWindow && mainWindow.isVisible()) {
                        mainWindow.webContents.send('window-show', { activeApp: data.app_name });
                    }
                })
                    .catch(e => {
                    // console.error('Main: Failed to get active app in background:', e.message);
                });
            }
        }
        catch (err) {
            // console.error('Main: Error in toggleWindow:', err.message);
            isToggling = false;
        }
    };
    // Create a fallback menu
    const menuTemplate = [
        {
            label: 'Prism',
            submenu: [
                { label: 'Toggle Window', accelerator: 'Alt+Space', click: toggleWindow },
                { label: 'Force Show', click: () => { mainWindow?.show(); mainWindow?.webContents.send('window-show'); } },
                { type: 'separator' },
                { role: 'quit' }
            ]
        }
    ];
    const menu = electron_1.Menu.buildFromTemplate(menuTemplate);
    electron_1.Menu.setApplicationMenu(menu);
    // Unregister all before registering to avoid conflicts
    electron_1.globalShortcut.unregisterAll();
    const isRegistered = electron_1.globalShortcut.register('Alt+Space', toggleWindow);
    if (!isRegistered) { }
});
electron_1.app.on('will-quit', () => {
    electron_1.globalShortcut.unregisterAll();
});
electron_1.app.on('before-quit', () => {
    isQuitting = true;
    stopPythonExecution();
    (0, overlay_1.destroyOverlay)();
    if (pythonProcess) {
        pythonProcess.kill();
    }
});
electron_1.app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        electron_1.app.quit();
    }
});
