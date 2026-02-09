import { app, BrowserWindow, ipcMain, globalShortcut, screen, net, Menu } from 'electron';
import path from 'path';
import { createTray } from './tray';
import { setupIpcHandlers } from './ipc';
import { spawn, ChildProcess, execSync } from 'child_process';
import fs from 'fs';
import Store from 'electron-store';
import { createOverlayWindow, destroyOverlay } from './overlay';

const store = new Store();
const debugLogPath = path.join(__dirname, '..', 'electron-main.log');

function debugLog(message: string) {
  try {
    fs.appendFileSync(debugLogPath, `${new Date().toISOString()} ${message}\n`);
  } catch {}
}

// Disable Electron security warnings
process.env.ELECTRON_DISABLE_SECURITY_WARNINGS = 'true';

let mainWindow: BrowserWindow | null = null;
let summaryWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;
let isQuitting = false;

if (!app.isPackaged) {
  // Use isolated userData during development to avoid profile lock/encryption issues.
  app.setPath('userData', path.join(app.getPath('appData'), 'PrismDev'));
}

async function stopPythonExecution() {
  try {
    await net.fetch('http://localhost:8000/stop', { method: 'POST' });
  } catch (err) {}
}

async function updateBackendVisibility(visible: boolean) {
  try {
    await net.fetch('http://localhost:8000/visibility', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ visible })
    });
  } catch (err) {}
}

export function createSummaryWindow(content: string) {
  if (summaryWindow) {
    summaryWindow.focus();
    summaryWindow.webContents.send('update-summary', content);
    return;
  }

  summaryWindow = new BrowserWindow({
    width: 600,
    height: 500,
    webPreferences: {
      preload: path.join(__dirname, '../preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    },
    title: 'Page Summary - Prism',
    backgroundColor: '#0f172a',
  });

  summaryWindow.loadFile(path.join(__dirname, '../renderer/index.html'), { query: { mode: 'summary' } });
  
  summaryWindow.webContents.on('did-finish-load', () => {
    setTimeout(() => {
      summaryWindow?.webContents.send('update-summary', content);
    }, 500);
  });

  summaryWindow.on('closed', () => {
    summaryWindow = null;
  });
}

async function waitForBackend(maxAttempts = 30): Promise<boolean> {
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const response = await net.fetch('http://localhost:8000/health');
      if (response.ok) {
        return true;
      }
    } catch (e) {
      // Backend not ready yet
    }
    await new Promise(r => setTimeout(r, 500));
  }
  return false;
}

function resolvePythonExecutable(): string {
  const fromEnv = process.env.PRISM_PYTHON_PATH;
  if (fromEnv && fs.existsSync(fromEnv)) {
    return fromEnv;
  }

  const local311 = path.join(process.env.USERPROFILE || '', 'AppData', 'Local', 'Programs', 'Python', 'Python311', 'python.exe');
  if (local311 && fs.existsSync(local311)) {
    return local311;
  }

  return 'python';
}

  async function startPythonBackend(): Promise<boolean> {
    const isPackaged = app.isPackaged;
    
    // First check if backend is already running (external dev server)
    try {
      const response = await net.fetch('http://localhost:8000/health');
      if (response.ok) {
        return true;
      }
    } catch (e) {}

    let pythonExecutable: string;
    let args: string[] = [];
    let cwd: string;

    if (isPackaged) {
      // Production: use the bundled executable
      const backendDir = path.join(process.resourcesPath, 'backend');
      pythonExecutable = path.join(backendDir, process.platform === 'win32' ? 'api.exe' : 'api');
      cwd = backendDir;
      args = []; // The frozen executable doesn't need script path args
    } else {
      // Development: use python and the script
      pythonExecutable = resolvePythonExecutable();
      const scriptPath = path.join(__dirname, '../../../python-backend/main.py');
      cwd = path.join(__dirname, '../../../python-backend');
      args = ['-u', scriptPath];
    }
    
    pythonProcess = spawn(pythonExecutable, args, {
      cwd,
      env: { 
        ...process.env,
        GEMINI_API_KEY: (store.get('GEMINI_API_KEY') as string) || process.env.GEMINI_API_KEY || ''
      },
      stdio: ['ignore', 'pipe', 'pipe']
    });
  
  pythonProcess.stdout?.on('data', () => {});
  pythonProcess.stderr?.on('data', () => {});
  pythonProcess.on('error', () => {});
  pythonProcess.on('exit', () => { pythonProcess = null; });

  // Wait for backend to be ready
  return await waitForBackend();
}

function createWindow() {
    const primaryDisplay = screen.getPrimaryDisplay();
    const { width: screenWidth, height: screenHeight, x: screenX, y: screenY } = primaryDisplay.workArea;
    
    const windowWidth = 520;
    const windowHeight = 250;
    const yPos = screenY + screenHeight - windowHeight - 10;

    const iconExt = process.platform === 'win32' ? 'ico' : 'png';
    const iconPath = !app.isPackaged
      ? path.join(__dirname, `../../assets/icon.${iconExt}`)
      : path.join(process.resourcesPath, `assets/icon.${iconExt}`);

    mainWindow = new BrowserWindow({
      width: windowWidth,
      height: windowHeight,
      x: screenX + Math.round((screenWidth - windowWidth) / 2),
      y: yPos,
      icon: iconPath,
      webPreferences: {
        preload: path.join(__dirname, '../preload.js'),
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

    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
    
    mainWindow.on('close', (event) => {
      if (!isQuitting) {
        event.preventDefault();
        stopPythonExecution();
        mainWindow?.hide();
      }
    });

    // Debug: log when window is ready
    mainWindow.webContents.on('did-finish-load', () => {});
      }
  
    app.whenReady().then(async () => {
      startPythonBackend().catch(() => {});
      createWindow();
      createTray(mainWindow);
      setupIpcHandlers();
      createOverlayWindow();
    
      let isToggling = false;
        const toggleWindow = async () => {
          if (isToggling) return;
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
              } else {
                updateBackendVisibility(true);
                
                const cursorPoint = screen.getCursorScreenPoint();


            const activeDisplay = screen.getDisplayNearestPoint(cursorPoint);
            const { width: sw, height: sh, x: sx, y: sy } = activeDisplay.workArea;
            const { width: ww, height: wh } = mainWindow.getBounds();
            const newX = sx + Math.round((sw - ww) / 2);
            const newY = sy + sh - wh - 10;
            
            mainWindow.setPosition(newX, newY);
            mainWindow.show();
            mainWindow.focus();
            
            isToggling = false;

            mainWindow.webContents.send('window-show', { activeApp: 'Desktop' });

            net.fetch('http://localhost:8000/active-app')
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
          } catch (err: any) {
            // console.error('Main: Error in toggleWindow:', err.message);
            isToggling = false;
          }
        };


          // Create a fallback menu
          const menuTemplate: any[] = [
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
          const menu = Menu.buildFromTemplate(menuTemplate);
          Menu.setApplicationMenu(menu);

          // Unregister all before registering to avoid conflicts
          globalShortcut.unregisterAll();

          const isRegistered = globalShortcut.register('Alt+Space', toggleWindow);
          if (!isRegistered) {}
        });


app.on('will-quit', () => {
  globalShortcut.unregisterAll();
});

app.on('before-quit', () => {
  isQuitting = true;
  stopPythonExecution();
  destroyOverlay();
  if (pythonProcess) {
    pythonProcess.kill();
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
