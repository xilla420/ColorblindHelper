# Colorblind Helper

A small always-on-top overlay that tells you the colour under your mouse cursor.
Works on Windows and macOS (Linux/X11 too).

## Features

- **Live colour under the cursor** – HEX, RGB and the closest named colour.
- **Descriptive mode** – plain-language description ("Light muted teal", "Dark brown",
  "Pale pink"), HSL / HSV / CMYK, contrast ratios, and swatches showing how the colour
  looks with protan, deutan and tritan vision (so you know which colours *you* may confuse).
- **Attach to cursor** – the overlay follows the mouse and is click-through.
- **Free mode** – detach it, drag it anywhere; it stays put. Scroll over it to resize,
  double-click to toggle descriptive mode, right-click for the menu.
- **Freeze** – lock the current colour so you can copy it.
- **Customisable** – dark/light theme, opacity, size, swatch size, font, corner radius,
  cursor offset, which fields are shown, 1×1 / 3×3 / 5×5 sampling, refresh rate.
- **Global hotkeys** (optional, via `pynput`) – copy HEX, freeze, attach, descriptive, show/hide.
- Settings persist across runs.

## Run

```bash
pip install -r requirements.txt
python main.py
```

or `python -m colorblind_helper`. The app lives in the system tray / menu bar.

### Default hotkeys

| Action                      | Global (pynput)     | Overlay focused (free mode) |
|-----------------------------|---------------------|-----------------------------|
| Copy HEX                    | Ctrl+Shift+C        | C                           |
| Freeze / unfreeze           | Ctrl+Shift+F        | Space or F                  |
| Attach / detach from cursor | Ctrl+Shift+A        | A                           |
| Toggle descriptive mode     | Ctrl+Shift+D        | D (or double-click)         |
| Show / hide overlay         | Ctrl+Shift+H        | Esc (hide)                  |
| Quit                        | –                   | Ctrl+Q                      |

All hotkeys can be changed in *Settings → Hotkeys*.

## macOS notes

- The first time you run it, macOS asks for **Screen Recording** permission for the
  terminal/app that launched it (System Settings → Privacy & Security). Without it the
  overlay cannot read screen pixels. Restart the app after granting.
- Global hotkeys additionally need **Accessibility** / **Input Monitoring**.

## Build a standalone executable

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name ColorblindHelper main.py
```

On macOS use `--windowed` instead of `--noconsole`; the result is `dist/ColorblindHelper.app`.

## Layout

```
colorblind_helper/
  app.py              tray icon, menus, hotkeys, wiring
  overlay.py          the overlay window (painting, drag, follow-cursor)
  colors.py           conversions, CIEDE2000 nearest name, descriptions, CVD simulation
  pixel.py            cross-platform pixel reader (GDI on Windows, Qt grab elsewhere)
  settings.py         persisted settings (JSON in the OS config dir)
  settings_dialog.py  settings window
  hotkeys.py          optional global hotkeys (pynput)
  names.py            CSS colour table
```
