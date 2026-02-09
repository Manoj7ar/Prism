"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.createTray = createTray;
const electron_1 = require("electron");
const path_1 = __importDefault(require("path"));
let tray = null;
function createTray(mainWindow) {
    const isDev = !electron_1.app.isPackaged;
    const iconExt = process.platform === 'win32' ? 'ico' : 'png';
    const iconPath = isDev
        ? path_1.default.join(__dirname, `../../assets/icon.${iconExt}`)
        : path_1.default.join(process.resourcesPath, `assets/icon.${iconExt}`);
    let icon = electron_1.nativeImage.createEmpty();
    try {
        icon = electron_1.nativeImage.createFromPath(iconPath);
    }
    catch (e) {
        console.error("Failed to load tray icon", e);
    }
    tray = new electron_1.Tray(icon);
    const contextMenu = electron_1.Menu.buildFromTemplate([
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
                electron_1.app.quit();
            }
        }
    ]);
    tray.setContextMenu(contextMenu);
    tray.setToolTip('Prism - AI Desktop Agent');
    tray.on('click', () => {
        if (mainWindow?.isVisible()) {
            mainWindow.hide();
        }
        else {
            mainWindow?.show();
        }
    });
}
