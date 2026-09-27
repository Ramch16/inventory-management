# Bevnetic POS · standalone desktop app

The POS prototype as its own desktop application for Windows, macOS and Linux.
It opens in its own window, not a browser, and works with no internet: the
fonts are bundled and nothing is loaded from the web. Printing opens the normal
print window, so receipts and reports go to the store's real printers.

The app shows the same screens as `design/pos-wireframes/index.html`. The
build copies that file in, so the desktop app and the online prototype never
drift apart.

## Run it on a store computer

| Computer | Download | How to open |
| --- | --- | --- |
| Windows 10/11 | `Bevnetic-POS-win32-x64.zip` | Unzip, open the folder, double-click **Bevnetic POS.exe**. Windows may show “Windows protected your PC” because the app isn't signed yet: click **More info → Run anyway**. Right-click the .exe → **Send to → Desktop (create shortcut)** for a desktop icon. |
| Mac (Apple silicon, M1 or later) | `Bevnetic-POS-darwin-arm64.zip` | Unzip and move **Bevnetic POS** to Applications. The first time, right-click it → **Open → Open** (the app isn't signed with an Apple certificate yet). |
| Mac (Intel) | `Bevnetic-POS-darwin-x64.zip` | Same as above. |
| Linux | `Bevnetic-POS-linux-x64.zip` | Unzip and run `./Bevnetic POS`. |

**Register lane (kiosk mode):** start the app with `--kiosk` for a locked,
full-screen register with no window controls. Press **Ctrl+Shift+Q** to quit.
On Windows, add `--kiosk` to the end of the shortcut's *Target* field.

**Shelf labels:** **Tools → Shelf Labels** (Ctrl+L / ⌘L) opens the standalone label page in its own window. Start the app with `--labels` to open only the labels page, for a back-office computer next to the label printer (`npm run labels` from source).

Other keys: **F11** full screen, **Ctrl + / Ctrl −** zoom, **Ctrl+R** reload.
Only one copy of the app runs per computer; opening it again brings the window
to the front.

## Build it yourself

Needs Node.js 20 or later.

```bash
cd desktop
npm install
npm start            # run from source
npm run kiosk        # run from source in kiosk mode
npm run build:win    # → dist/Bevnetic POS-win32-x64/
npm run build:mac    # → dist/Bevnetic POS-darwin-arm64/ and -x64/
npm run build:linux  # → dist/Bevnetic POS-linux-x64/
```

`npm run sync` (run automatically by the commands above) copies the prototype
into `app/`, swaps the Google Fonts link for the bundled fonts, and replaces the
“printing is simulated” notes.

## Before rolling out to stores

- **Code signing**: sign the Windows .exe (code-signing certificate) and the Mac
  app (Apple Developer ID + notarization) so the security warnings go away.
- **Installer and updates**: wrap the build in an installer (for example
  electron-builder with NSIS on Windows and a DMG on Mac) with automatic updates.
- **Data**: the prototype keeps its demo data in memory, so it resets when the
  app closes. The real app keeps a local database on each lane (for example
  SQLite) that syncs with the cloud, so sales keep working when the internet is
  down, as the Offline screen describes.
- **Hardware**: receipt printer, cash drawer, barcode scanner and card reader
  are driven from the desktop app (ESC/POS over USB or network for the printer
  and drawer; the scanner types into the scan box like a keyboard).
