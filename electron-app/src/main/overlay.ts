import { BrowserWindow, screen } from 'electron';
import path from 'path';

let overlayWindow: BrowserWindow | null = null;
let hideTimer: NodeJS.Timeout | null = null;

export function createOverlayWindow(): BrowserWindow {
  if (overlayWindow && !overlayWindow.isDestroyed()) {
    return overlayWindow;
  }

  const primaryDisplay = screen.getPrimaryDisplay();
  const { width, height } = primaryDisplay.bounds;

  overlayWindow = new BrowserWindow({
    width,
    height,
    x: 0,
    y: 0,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    alwaysOnTop: true,
    skipTaskbar: true,
    focusable: false,
    resizable: false,
    movable: false,
    show: false,
    hasShadow: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Keep overlay above normal app windows so edge animation is always visible.
  overlayWindow.setAlwaysOnTop(true, 'screen-saver');
  overlayWindow.setIgnoreMouseEvents(true, { forward: true });
  overlayWindow.setVisibleOnAllWorkspaces(true);

  const overlayHtml = `
      <!DOCTYPE html>
      <html>
      <head>
        <style>
          * { margin: 0; padding: 0; box-sizing: border-box; }
          html, body {
            width: 100vw;
            height: 100vh;
            background: transparent;
            overflow: hidden;
          }
          .border-container {
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: 999999;
            opacity: 0;
            animation: fadeIn 0.7s cubic-bezier(0.23, 1, 0.32, 1) forwards;
          }
            .border-container.hiding {
              animation: fadeOut 0.5s cubic-bezier(0.4, 0, 0.2, 1) forwards;
            }
          @keyframes fadeIn {
            0% { opacity: 0; }
            100% { opacity: 1; }
          }
            @keyframes fadeOut {
              0% { opacity: 1; }
              100% { opacity: 0; }
            }
            .glow-top, .glow-right, .glow-bottom, .glow-left {
              position: absolute;
              filter: blur(44px);
              opacity: 0;
            }
            .line-top, .line-right, .line-bottom, .line-left {
              position: absolute;
              background: #4285F4;
              box-shadow: 0 0 14px rgba(66, 133, 244, 0.95), 0 0 26px rgba(66, 133, 244, 0.8);
              opacity: 0;
              animation: lineFadeIn 0.6s ease-out forwards, linePulse 1.8s ease-in-out infinite;
            }
            .line-top, .line-bottom { left: 0; right: 0; height: 3px; }
            .line-left, .line-right { top: 0; bottom: 0; width: 3px; }
            .line-top { top: 0; }
            .line-bottom { bottom: 0; }
            .line-left { left: 0; }
            .line-right { right: 0; }
            @keyframes lineFadeIn {
              0% { opacity: 0; }
              100% { opacity: 0.92; }
            }
            @keyframes linePulse {
              0%, 100% { opacity: 0.78; }
              50% { opacity: 1; }
            }
            @keyframes glowFadeIn {
              0% { opacity: 0; }
              100% { opacity: 0.86; }
            }
              .glow-top {
                top: -48px; left: 0; right: 0; height: 96px;
                background: linear-gradient(90deg, #4285F4, rgba(66, 133, 244, 1), #4285F4, rgba(66, 133, 244, 1), #4285F4);
                background-size: 300% 100%;
                -webkit-mask-image: linear-gradient(to bottom, black 16%, transparent 84%);
                animation: glowFadeIn 1s cubic-bezier(0.4, 0, 0.2, 1) forwards, slideGlow 18s ease-in-out infinite, breathe 12s ease-in-out infinite;
              }
              .glow-bottom {
                bottom: -48px; left: 0; right: 0; height: 96px;
                background: linear-gradient(90deg, #4285F4, rgba(66, 133, 244, 1), #4285F4, rgba(66, 133, 244, 1), #4285F4);
                background-size: 300% 100%;
                -webkit-mask-image: linear-gradient(to top, black 16%, transparent 84%);
                animation: glowFadeIn 1s cubic-bezier(0.4, 0, 0.2, 1) forwards, slideGlow 18s ease-in-out infinite reverse, breathe 12s ease-in-out infinite 2s;
              }
              .glow-left {
                top: 0; bottom: 0; left: -48px; width: 96px;
                background: linear-gradient(180deg, #4285F4, rgba(66, 133, 244, 1), #4285F4, rgba(66, 133, 244, 1), #4285F4);
                background-size: 100% 300%;
                -webkit-mask-image: linear-gradient(to right, black 16%, transparent 84%);
                animation: glowFadeIn 1s cubic-bezier(0.4, 0, 0.2, 1) forwards, slideGlowVertical 18s ease-in-out infinite, breathe 12s ease-in-out infinite 1s;
              }
              .glow-right {
                top: 0; bottom: 0; right: -48px; width: 96px;
                background: linear-gradient(180deg, #4285F4, rgba(66, 133, 244, 1), #4285F4, rgba(66, 133, 244, 1), #4285F4);
                background-size: 100% 300%;
                -webkit-mask-image: linear-gradient(to left, black 16%, transparent 84%);
                animation: glowFadeIn 1s cubic-bezier(0.4, 0, 0.2, 1) forwards, slideGlowVertical 18s ease-in-out infinite reverse, breathe 12s ease-in-out infinite 3s;
              }
            @keyframes slideGlow {
              0%, 100% { background-position: 0% 50%; }
              50% { background-position: 100% 50%; }
            }
            @keyframes slideGlowVertical {
              0%, 100% { background-position: 50% 0%; }
              50% { background-position: 50% 100%; }
            }
            @keyframes breathe {
              0%, 100% { transform: scale(1); opacity: 0.72; }
              50% { transform: scale(1.01); opacity: 0.95; }
            }
          </style>
        </head>
        <body>
          <div class="border-container" id="container">
            <div class="line-top"></div>
            <div class="line-right"></div>
            <div class="line-bottom"></div>
            <div class="line-left"></div>
            <div class="glow-top"></div>
            <div class="glow-right"></div>
            <div class="glow-bottom"></div>
            <div class="glow-left"></div>
          </div>
        </body>
        </html>
      `;

  overlayWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(overlayHtml)}`);

  overlayWindow.on('closed', () => {
    overlayWindow = null;
  });

  return overlayWindow;
}

function getActiveDisplayBounds() {
  const cursorPoint = screen.getCursorScreenPoint();
  const activeDisplay = screen.getDisplayNearestPoint(cursorPoint);
  return activeDisplay.bounds;
}

export function showOverlay(): void {
  if (!overlayWindow || overlayWindow.isDestroyed()) {
    createOverlayWindow();
  }
  if (hideTimer) {
    clearTimeout(hideTimer);
    hideTimer = null;
  }
  
  const { width, height, x, y } = getActiveDisplayBounds();
  overlayWindow?.setBounds({ x, y, width, height });
  overlayWindow?.webContents.executeJavaScript(`
    const el = document.getElementById('container');
    if (el) {
      el.classList.remove('hiding');
      void el.offsetWidth;
      el.style.animation = 'none';
      void el.offsetWidth;
      el.style.animation = 'fadeIn 0.7s cubic-bezier(0.23, 1, 0.32, 1) forwards';
    }
  `).catch(() => {});
  overlayWindow?.showInactive();
}

export function hideOverlay(): void {
  if (overlayWindow && !overlayWindow.isDestroyed()) {
    if (hideTimer) {
      clearTimeout(hideTimer);
      hideTimer = null;
    }
    overlayWindow.webContents.executeJavaScript(`
      const el = document.getElementById('container');
      if (el) {
        el.classList.remove('hiding');
        void el.offsetWidth;
        el.classList.add('hiding');
      }
    `).catch(() => {});
    hideTimer = setTimeout(() => {
      if (overlayWindow && !overlayWindow.isDestroyed()) {
        overlayWindow.hide();
      }
      hideTimer = null;
    }, 500);
  }
}

export function destroyOverlay(): void {
  if (hideTimer) {
    clearTimeout(hideTimer);
    hideTimer = null;
  }
  if (overlayWindow && !overlayWindow.isDestroyed()) {
    overlayWindow.close();
    overlayWindow = null;
  }
}

export function getOverlayWindow(): BrowserWindow | null {
  return overlayWindow;
}
