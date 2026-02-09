import { ipcMain, net, BrowserWindow, app } from 'electron';
import { createSummaryWindow } from './main';
import { showOverlay, hideOverlay } from './overlay';
import fs from 'fs';
import path from 'path';
import Store from 'electron-store';

const store = new Store();
const PRESETS_FILE = path.join(app.getPath('userData'), 'presets.json');

function ensurePresetsFile() {
  if (!fs.existsSync(PRESETS_FILE)) {
    fs.writeFileSync(PRESETS_FILE, JSON.stringify([]));
  }
}

export function setupIpcHandlers() {
    ensurePresetsFile();

    ipcMain.handle('get-presets', async () => {
        try {
          ensurePresetsFile();
          const data = fs.readFileSync(PRESETS_FILE, 'utf8');
          return JSON.parse(data);
        } catch (error: any) {
          // console.error('Failed to get presets:', error);
          return [];
        }
      });

      ipcMain.handle('save-preset', async (event, preset: any) => {
        try {
          ensurePresetsFile();
          const data = fs.readFileSync(PRESETS_FILE, 'utf8');
          let presets = JSON.parse(data);
          
          const index = presets.findIndex((p: any) => p.id === preset.id);
          if (index >= 0) {
            presets[index] = preset;
          } else {
            presets.push(preset);
          }
          
          fs.writeFileSync(PRESETS_FILE, JSON.stringify(presets, null, 2));
          return { success: true };
        } catch (error: any) {
          // console.error('Failed to save preset:', error);
          return { success: false, error: error.message };
        }
      });

      ipcMain.handle('delete-preset', async (event, presetId: string) => {
        try {
          ensurePresetsFile();
          const data = fs.readFileSync(PRESETS_FILE, 'utf8');
          let presets = JSON.parse(data);
          presets = presets.filter((p: any) => p.id !== presetId);
          fs.writeFileSync(PRESETS_FILE, JSON.stringify(presets, null, 2));
          return { success: true };
        } catch (error: any) {
          // console.error('Failed to delete preset:', error);
          return { success: false, error: error.message };
        }
      });


    ipcMain.handle('execute-command', async (event, command: string) => {
      try {
        const params = new URLSearchParams();
        params.append('command', command);
        
        const response = await net.fetch('http://localhost:8000/execute', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: params.toString()
        });
        return await response.json();
      } catch (error: any) {
        return { success: false, error: error.message };
      }
    });

    ipcMain.handle('execute-preset', async (event, steps: string[], history: any[]) => {
      try {
        const response = await net.fetch('http://localhost:8000/execute-preset', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ steps, history })
        });
        return await response.json();
      } catch (error: any) {
        return { success: false, error: error.message };
      }
    });

    ipcMain.handle('stop-execution', async () => {
      try {
        const response = await net.fetch('http://localhost:8000/stop', {
          method: 'POST'
        });
        return await response.json();
      } catch (error: any) {
        return { success: false, error: error.message };
      }
    });

    ipcMain.handle('get-context', async () => {
    try {
      const response = await net.fetch('http://localhost:8000/context');
      return await response.json();
    } catch (error: any) {
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('show-summary', async (event, content: string) => {
    createSummaryWindow(content);
    return { success: true };
  });

    ipcMain.handle('resize-window', (event, width: number, height: number) => {
        const win = BrowserWindow.fromWebContents(event.sender);
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


      ipcMain.handle('get-tasks', async () => {
        try {
          const response = await net.fetch('http://localhost:8000/tasks');
          return await response.json();
        } catch (error: any) {
          return { success: false, error: error.message };
        }
      });

      ipcMain.handle('hide-window', (event) => {
        const win = BrowserWindow.fromWebContents(event.sender);
        if (win) {
          win.hide();
        }
        return { success: true };
      });

    ipcMain.handle('get-memory-status', async () => {
      try {
        const response = await net.fetch('http://localhost:8000/memory-status');
        return await response.json();
      } catch (error: any) {
        return { success: false, error: error.message };
      }
    });

    ipcMain.handle('clear-memory', async () => {
      try {
        const response = await net.fetch('http://localhost:8000/memory-clear', {
          method: 'POST'
        });
        return await response.json();
      } catch (error: any) {
        return { success: false, error: error.message };
      }
    });

    ipcMain.handle('set-api-key', async (event, key: string) => {
      try {
        store.set('GEMINI_API_KEY', key);
        // Also update backend if it's running
        try {
          await net.fetch('http://localhost:8000/set-key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key })
          });
        } catch (e) {}
        return { success: true };
      } catch (error: any) {
        return { success: false, error: error.message };
      }
    });

    ipcMain.handle('get-api-key', async () => {
      return store.get('GEMINI_API_KEY') || '';
    });

    ipcMain.handle('show-automation-overlay', async (event, show: boolean) => {
      if (show) {
        showOverlay();
      } else {
        hideOverlay();
      }
      return { success: true };
    });
}


