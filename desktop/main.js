// Bevnetic POS · desktop shell
// Runs the POS as a standalone app: its own window, no browser, works with no internet.
// Start with --kiosk for a locked full-screen register (Ctrl+Shift+Q quits).
const { app, BrowserWindow, Menu, shell, globalShortcut } = require('electron');
const path = require('path');

const kiosk = process.argv.includes('--kiosk');
let win;

function createWindow() {
  win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: 'Bevnetic POS',
    icon: path.join(__dirname, 'build', 'icon.png'),
    backgroundColor: '#13202A',
    autoHideMenuBar: true,
    kiosk,
    show: false,
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  win.loadFile(path.join(__dirname, 'app', 'index.html'));
  win.once('ready-to-show', () => { win.maximize(); win.show(); });

  // keep the POS inside its own window: any outside link opens in the normal browser
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('file:') && url.endsWith('shelf-labels.html')) { openLabels(); return { action: 'deny' }; }
    if (/^https?:/.test(url)) shell.openExternal(url);
    return { action: 'deny' };
  });
  win.webContents.on('will-navigate', (e, url) => { if (!url.startsWith('file:')) { e.preventDefault(); shell.openExternal(url); } });
}

// standalone Shelf Labels page in its own window (one at a time)
let labelsWin;
function openLabels() {
  if (labelsWin && !labelsWin.isDestroyed()) { labelsWin.focus(); return; }
  labelsWin = new BrowserWindow({
    width: 1280, height: 860, minWidth: 900, minHeight: 600, title: 'Bevnetic Shelf Labels',
    icon: path.join(__dirname, 'build', 'icon.png'), backgroundColor: '#13202A', autoHideMenuBar: true,
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  labelsWin.loadFile(path.join(__dirname, 'app', 'shelf-labels.html'));
}

// one copy of the POS per computer
if (!app.requestSingleInstanceLock()) app.quit();
app.on('second-instance', () => { if (win) { if (win.isMinimized()) win.restore(); win.focus(); } });

app.whenReady().then(() => {
  if (process.argv.includes('--labels')) { Menu.setApplicationMenu(null); openLabels(); return; }
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    { label: 'Bevnetic POS', submenu: [{ role: 'reload' }, { role: 'togglefullscreen' }, { type: 'separator' }, { role: 'quit' }] },
    { label: 'Tools', submenu: [{ label: 'Shelf Labels', accelerator: 'CommandOrControl+L', click: openLabels }] },
    { label: 'View', submenu: [{ role: 'zoomIn' }, { role: 'zoomOut' }, { role: 'resetZoom' }] },
  ]));
  createWindow();
  if (kiosk) globalShortcut.register('CommandOrControl+Shift+Q', () => app.quit());
});
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
app.on('will-quit', () => globalShortcut.unregisterAll());
