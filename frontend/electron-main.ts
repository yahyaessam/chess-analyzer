import { app, BrowserWindow, globalShortcut, ipcMain, Menu, nativeImage, screen, Tray } from 'electron';
import * as os from 'os';
import * as path from 'path';

const userDataDir = path.join(os.homedir(), '.chess-analyzer-overlay');
app.setPath('userData', userDataDir);
app.setPath('cache', path.join(userDataDir, 'Cache'));

let win: BrowserWindow | null = null;
let tray: Tray | null = null;

function toggleOverlay(): void {
  if (!win) return;
  if (win.isVisible()) {
    win.hide();
  } else {
    win.showInactive();
    win.setAlwaysOnTop(true, 'screen-saver');
    win.setIgnoreMouseEvents(true, { forward: true });
  }
}

function createWindow(): void {
  const display = screen.getPrimaryDisplay();

  win = new BrowserWindow({
    x: display.bounds.x,
    y: display.bounds.y,
    width: display.bounds.width,
    height: display.bounds.height,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    fullscreen: true,
    focusable: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      backgroundThrottling: false,
    },
  });

  win.setIgnoreMouseEvents(true, { forward: true });
  win.loadFile(path.join(__dirname, '../dist/frontend/browser/index.html'));

  win.webContents.on('console-message', (_event, _level, message) => {
    console.log('renderer:', message);
  });

  win.on('closed', () => {
    win = null;
  });
}

app.whenReady().then(() => {
  createWindow();
  console.log('Electron main ready. Registering global shortcuts...');

  const hok = globalShortcut.register('Ctrl+Shift+H', () => {
    console.log('Ctrl+Shift+H pressed, toggling overlay');
    toggleOverlay();
  });
  console.log('Ctrl+Shift+H registered:', hok);

  const cok = globalShortcut.register('Ctrl+Shift+C', () => {
    console.log('Ctrl+Shift+C pressed, sending calibrate IPC');
    win?.webContents.send('calibrate');
  });
  console.log('Ctrl+Shift+C registered:', cok);

  const iconPath = path.join(__dirname, '../dist/frontend/browser/assets/icon.png');
  const icon = nativeImage.createFromPath(iconPath);
  tray = new Tray(icon.isEmpty() ? nativeImage.createEmpty() : icon);
  tray.setToolTip('Chess Analyzer');
  const contextMenu = Menu.buildFromTemplate([
    { label: 'Show/Hide Overlay', click: toggleOverlay },
    { label: 'Calibrate Board', click: () => win?.webContents.send('calibrate') },
    { type: 'separator' },
    { label: 'Quit', click: () => app.quit() },
  ]);
  tray.setContextMenu(contextMenu);
  tray.on('double-click', toggleOverlay);
});

app.on('window-all-closed', () => {
  globalShortcut.unregisterAll();
  app.quit();
});

ipcMain.on('set-ignore-mouse-events', (_event: unknown, ignore: boolean) => {
  win?.setIgnoreMouseEvents(ignore, { forward: true });
});

ipcMain.on('toggle-overlay', () => {
  toggleOverlay();
});
