import { Tray, Menu, BrowserWindow, app, nativeImage } from 'electron';
import path from 'path';

let tray: Tray | null = null;

export function createTray(mainWindow: BrowserWindow | null) {
  const isDev = !app.isPackaged;
  const iconExt = process.platform === 'win32' ? 'ico' : 'png';
  const iconPath = isDev
    ? path.join(__dirname, `../../assets/icon.${iconExt}`)
    : path.join(process.resourcesPath, `assets/icon.${iconExt}`);

  let icon = nativeImage.createEmpty();
  try {
    icon = nativeImage.createFromPath(iconPath);
  } catch (e) {
    console.error("Failed to load tray icon", e);
  }

  tray = new Tray(icon);

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Open Prism',
      click: () => {
        mainWindow?.show();
      }
    },
    {
      label: 'Start Voice Command',
      click: () => {
        mainWindow?.show();
        mainWindow?.webContents.send('start-recording');
      }
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        app.quit();
      }
    }
  ]);

  tray.setContextMenu(contextMenu);
  tray.setToolTip('Prism - AI Desktop Agent');

  tray.on('click', () => {
    if (mainWindow?.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow?.show();
    }
  });
}
