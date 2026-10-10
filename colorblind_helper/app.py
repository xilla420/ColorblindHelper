"""Application wiring: tray icon, menus, hotkeys, overlay, settings window,
run-at-startup and single-instance handling."""
from __future__ import annotations

import getpass
import sys

from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import __version__, autostart
from .colors import CVD_LABELS
from .hotkeys import HotkeyManager, pynput_available
from .icon import app_icon
from .overlay import OverlayWindow
from .pixel import PixelReader
from .settings import APP_NAME, load_settings, save_settings
from .settings_window import SettingsWindow
from .themes import THEMES, get_theme, menu_stylesheet, palette_for


class StayOpenMenu(QMenu):
    """Menu whose checkable items toggle without closing the menu."""

    def _toggle_active(self) -> bool:
        act = self.activeAction()
        if act is not None and act.isCheckable() and act.isEnabled() and act.menu() is None:
            act.trigger()
            return True
        return False

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self._toggle_active():
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e) -> None:
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space) \
                and self._toggle_active():
            e.accept()
            return
        super().keyPressEvent(e)


def _instance_name() -> str:
    try:
        user = getpass.getuser()
    except Exception:
        user = "user"
    return f"{APP_NAME}-{user}"


class ColorblindHelperApp(QObject):
    def __init__(self, argv: list[str]) -> None:
        self.qapp = QApplication.instance() or QApplication(argv)
        super().__init__()
        self.qapp.setApplicationName(APP_NAME)
        self.qapp.setApplicationDisplayName("Colorblind Helper")
        self.qapp.setOrganizationName(APP_NAME)
        self.qapp.setApplicationVersion(__version__)
        self.qapp.setQuitOnLastWindowClosed(False)
        self.qapp.setStyle("Fusion")
        self.qapp.setWindowIcon(app_icon())
        self.autostarted = autostart.STARTUP_FLAG in argv

        # Single instance: if one is already running, ask it to show its settings.
        self.already_running = self._signal_existing_instance()
        if self.already_running:
            return
        self._server = QLocalServer(self)
        QLocalServer.removeServer(_instance_name())
        self._server.listen(_instance_name())
        self._server.newConnection.connect(self._on_second_instance)

        self.settings = load_settings()
        self.reader = PixelReader()
        self.overlay = OverlayWindow(self.settings, self.reader)
        self.window: SettingsWindow | None = None

        ov = self.overlay
        ov.contextMenuRequested.connect(self._show_menu_at)
        ov.toggleDescriptiveRequested.connect(self.toggle_descriptive)
        ov.toggleAttachRequested.connect(self.toggle_attach)
        ov.toggleFreezeRequested.connect(self.toggle_freeze)
        ov.copyRequested.connect(self.copy_hex)
        ov.hideRequested.connect(lambda: self.set_visible(False))
        ov.quitRequested.connect(self.quit)
        ov.settingsChanged.connect(self._on_settings_changed)
        ov.colorChanged.connect(self._on_color)

        self._build_menu()
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip("Colorblind Helper")
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

        self.hotkeys = HotkeyManager(self)
        self.hotkeys.triggered.connect(self._on_hotkey)
        self.hotkeys.error.connect(self._notify)
        self.hotkeys.apply(self.settings.hotkeys_enabled, self.settings.hotkey_map())

        self._apply_ui_theme()
        self._sync_autostart()
        self.overlay.show()
        self._sync_actions()

        if self.settings.first_run and not self.autostarted:
            self.settings.first_run = False
            save_settings(self.settings)
            self.open_settings()
        if sys.platform == "darwin":
            self._mac_permission_hint()

    # ------------------------------------------------------------------ single instance
    @staticmethod
    def _signal_existing_instance() -> bool:
        sock = QLocalSocket()
        sock.connectToServer(_instance_name())
        if sock.waitForConnected(300):
            sock.write(b"show")
            sock.waitForBytesWritten(300)
            sock.disconnectFromServer()
            return True
        return False

    def _on_second_instance(self) -> None:
        conn = self._server.nextPendingConnection()
        if conn is not None:
            conn.disconnectFromServer()
        self.set_visible(True)
        self.open_settings()

    # ------------------------------------------------------------------ menu / tray
    def _build_menu(self) -> None:
        self.menu = QMenu()
        title = QAction("Colorblind Helper", self.menu)
        title.setEnabled(False)
        self.act_attach = QAction("Follow cursor", self.menu, checkable=True)
        self.act_attach.triggered.connect(self.toggle_attach)
        self.act_desc = QAction("Descriptive mode", self.menu, checkable=True)
        self.act_desc.triggered.connect(self.toggle_descriptive)
        self.act_freeze = QAction("Freeze colour", self.menu, checkable=True)
        self.act_freeze.triggered.connect(self.toggle_freeze)
        self.act_visible = QAction("Show overlay", self.menu, checkable=True)
        self.act_visible.triggered.connect(self.set_visible)

        self.act_copy_hex = QAction("Copy HEX", self.menu)
        self.act_copy_hex.triggered.connect(self.copy_hex)
        self.act_copy_rgb = QAction("Copy RGB", self.menu)
        self.act_copy_rgb.triggered.connect(self.copy_rgb)
        self.act_copy_desc = QAction("Copy description", self.menu)
        self.act_copy_desc.triggered.connect(self.copy_description)

        sims = StayOpenMenu("Colour-blind simulations", self.menu)
        self.sim_actions: dict[str, QAction] = {}
        for kind, label in CVD_LABELS.items():
            act = QAction(label, sims, checkable=True)
            act.triggered.connect(lambda checked, k=kind: self.set_simulation(k, checked))
            sims.addAction(act)
            self.sim_actions[kind] = act

        themes = QMenu("Overlay theme", self.menu)
        self.theme_actions: dict[str, QAction] = {}
        for key in ("match", *THEMES):
            act = QAction("Match app" if key == "match" else THEMES[key].name, themes,
                          checkable=True)
            act.triggered.connect(lambda _=False, k=key: self.set_overlay_theme(k))
            themes.addAction(act)
            self.theme_actions[key] = act

        act_settings = QAction("Settings…", self.menu)
        act_settings.triggered.connect(self.open_settings)
        act_quit = QAction("Quit", self.menu)
        act_quit.triggered.connect(self.quit)

        m = self.menu
        m.addAction(title)
        m.addSeparator()
        m.addAction(self.act_attach)
        m.addAction(self.act_desc)
        m.addAction(self.act_freeze)
        m.addAction(self.act_visible)
        m.addSeparator()
        m.addAction(self.act_copy_hex)
        m.addAction(self.act_copy_rgb)
        m.addAction(self.act_copy_desc)
        m.addSeparator()
        m.addMenu(sims)
        m.addMenu(themes)
        m.addAction(act_settings)
        m.addSeparator()
        m.addAction(act_quit)

    def _sync_actions(self) -> None:
        s = self.settings
        pairs = [(self.act_attach, s.attach_to_cursor),
                 (self.act_desc, s.descriptive_mode),
                 (self.act_freeze, self.overlay.frozen),
                 (self.act_visible, self.overlay.isVisible())]
        pairs += [(a, getattr(s, f"sim_{k}")) for k, a in self.sim_actions.items()]
        pairs += [(a, s.overlay_theme == k) for k, a in self.theme_actions.items()]
        for act, val in pairs:
            act.blockSignals(True)
            act.setChecked(bool(val))
            act.blockSignals(False)
        has = self.overlay.info is not None
        for act in (self.act_copy_hex, self.act_copy_rgb, self.act_copy_desc):
            act.setEnabled(has)

    def _show_menu_at(self, pos: QPoint) -> None:
        self._sync_actions()
        self.menu.popup(pos)

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger and sys.platform != "darwin":
            self.set_visible(not self.overlay.isVisible())
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_settings()
        elif reason == QSystemTrayIcon.ActivationReason.Context:
            self._sync_actions()

    def _notify(self, text: str, title: str = "Colorblind Helper") -> None:
        if self.tray.isVisible() and QSystemTrayIcon.supportsMessages():
            self.tray.showMessage(title, text, app_icon(), 5000)
        else:
            print(f"{title}: {text}", file=sys.stderr)

    def _mac_permission_hint(self) -> None:
        if self.overlay.info is None and self.reader.backend == "qt":
            self._notify("If colours don't update, allow Screen Recording for this app in "
                         "System Settings → Privacy & Security, then restart it.")

    # ------------------------------------------------------------------ actions
    def toggle_attach(self) -> None:
        self.settings.attach_to_cursor = not self.settings.attach_to_cursor
        self._on_settings_changed()

    def toggle_descriptive(self) -> None:
        self.settings.descriptive_mode = not self.settings.descriptive_mode
        self._on_settings_changed()

    def toggle_freeze(self) -> None:
        self.overlay.set_frozen(not self.overlay.frozen)
        self._sync_actions()

    def set_visible(self, visible: bool) -> None:
        self.overlay.setVisible(bool(visible))
        self._sync_actions()

    def set_simulation(self, kind: str, enabled: bool) -> None:
        setattr(self.settings, f"sim_{kind}", bool(enabled))
        if enabled:
            self.settings.show_simulations = True
        self._on_settings_changed()

    def set_overlay_theme(self, key: str) -> None:
        self.settings.overlay_theme = key
        self._on_settings_changed()

    def _copy(self, text: str, add_to_palette: bool = True) -> None:
        self.qapp.clipboard().setText(text)
        self.overlay.flash_copied()
        if add_to_palette and self.overlay.info is not None:
            self.settings.add_to_palette(self.overlay.info.hex(True))
            self._on_palette_changed()

    def _on_palette_changed(self) -> None:
        if self.window is not None:
            self.window.refresh()
        save_settings(self.settings)

    def copy_hex(self) -> None:
        if self.overlay.info:
            self._copy(self.overlay.info.hex(self.settings.uppercase_hex))

    def copy_rgb(self) -> None:
        if self.overlay.info:
            self._copy("rgb({}, {}, {})".format(*self.overlay.info.rgb))

    def copy_description(self) -> None:
        info = self.overlay.info
        if info:
            self._copy(f"{info.description} ({info.hex(self.settings.uppercase_hex)}, "
                       f"closest: {info.name})")

    def open_settings(self) -> None:
        if self.window is None:
            self.window = SettingsWindow(self.settings, pynput_available())
            self.window.changed.connect(self._on_settings_changed)
            self.window.quitRequested.connect(self.quit)
            self.window.copyRequested.connect(
                lambda hx: self._copy(hx if self.settings.uppercase_hex else hx.lower(),
                                      add_to_palette=False))
            self.window.paletteChanged.connect(self._on_palette_changed)
            self.window.set_live_color(self.overlay.info)
        self.window.refresh()
        self.window.show()
        self.window.setWindowState(self.window.windowState() & ~Qt.WindowState.WindowMinimized)
        self.window.raise_()
        self.window.activateWindow()

    def quit(self) -> None:
        save_settings(self.settings)
        self.hotkeys.stop()
        self.tray.hide()
        # exit(), not quit(): Qt 6's quit() closes windows first, and the settings
        # window ignores close (it hides to tray), which would cancel the quit.
        self.qapp.exit(0)

    # ------------------------------------------------------------------ plumbing
    def _apply_ui_theme(self) -> None:
        t = get_theme(self.settings.ui_theme)
        self.qapp.setPalette(palette_for(t))
        self.qapp.setStyleSheet(menu_stylesheet(t))
        if self.window is not None:
            self.window.apply_theme()

    def _sync_autostart(self) -> None:
        want = self.settings.run_at_startup
        try:
            # Re-register when enabled so a moved exe/script keeps working.
            if want or autostart.is_enabled():
                autostart.set_enabled(want)
        except OSError as exc:
            self.settings.run_at_startup = autostart.is_enabled()
            self._notify(f"Could not change the startup setting: {exc}")

    def _on_color(self, info) -> None:
        if self.window is not None and self.window.isVisible():
            self.window.set_live_color(info)

    def _on_settings_changed(self) -> None:
        self.overlay.apply_settings()
        self.hotkeys.apply(self.settings.hotkeys_enabled, self.settings.hotkey_map())
        self._apply_ui_theme()
        self._sync_autostart()
        if self.window is not None:
            self.window.refresh()
        self._sync_actions()
        save_settings(self.settings)

    def _on_hotkey(self, action: str) -> None:
        {
            "copy_hex": self.copy_hex,
            "freeze": self.toggle_freeze,
            "toggle_attach": self.toggle_attach,
            "toggle_descriptive": self.toggle_descriptive,
            "toggle_visible": lambda: self.set_visible(not self.overlay.isVisible()),
        }.get(action, lambda: None)()

    def run(self) -> int:
        if self.already_running:
            return 0
        return self.qapp.exec()


def main(argv: list[str] | None = None) -> int:
    app = ColorblindHelperApp(sys.argv if argv is None else argv)
    return app.run()
