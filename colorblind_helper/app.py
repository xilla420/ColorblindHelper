"""Application wiring: tray icon, menus, hotkeys, overlay and settings."""
from __future__ import annotations

import sys

from PySide6.QtCore import QObject, QPoint, QRectF, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import __version__
from .colors import CVD_LABELS
from .hotkeys import HotkeyManager, pynput_available
from .overlay import OverlayWindow
from .pixel import PixelReader
from .settings import APP_NAME, load_settings, save_settings
from .settings_dialog import SettingsDialog


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


def make_icon(size: int = 64) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(Qt.PenStyle.NoPen)
    rect = QRectF(3, 3, size - 6, size - 6)
    for i, col in enumerate(("#E53935", "#FDD835", "#43A047", "#1E88E5")):
        p.setBrush(QColor(col))
        p.drawPie(rect, i * 90 * 16, 90 * 16)
    p.setBrush(QColor(255, 255, 255))
    p.drawEllipse(rect.center(), size * 0.2, size * 0.2)
    p.setBrush(QColor(30, 30, 30))
    p.drawEllipse(rect.center(), size * 0.09, size * 0.09)
    p.end()
    return QIcon(pm)


class ColorblindHelperApp(QObject):
    def __init__(self, argv: list[str]) -> None:
        self.qapp = QApplication(argv)
        super().__init__()
        self.qapp.setApplicationName(APP_NAME)
        self.qapp.setApplicationDisplayName("Colorblind Helper")
        self.qapp.setOrganizationName(APP_NAME)
        self.qapp.setApplicationVersion(__version__)
        self.qapp.setQuitOnLastWindowClosed(False)
        self.qapp.setWindowIcon(make_icon())

        self.settings = load_settings()
        self.reader = PixelReader()
        self.overlay = OverlayWindow(self.settings, self.reader)
        self.dialog: SettingsDialog | None = None

        ov = self.overlay
        ov.contextMenuRequested.connect(self._show_menu_at)
        ov.toggleDescriptiveRequested.connect(self.toggle_descriptive)
        ov.toggleAttachRequested.connect(self.toggle_attach)
        ov.toggleFreezeRequested.connect(self.toggle_freeze)
        ov.copyRequested.connect(self.copy_hex)
        ov.hideRequested.connect(lambda: self.set_visible(False))
        ov.quitRequested.connect(self.quit)
        ov.settingsChanged.connect(self._on_settings_changed)

        self._build_menu()
        self.tray = QSystemTrayIcon(make_icon(), self)
        self.tray.setToolTip("Colorblind Helper")
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

        self.hotkeys = HotkeyManager(self)
        self.hotkeys.triggered.connect(self._on_hotkey)
        self.hotkeys.error.connect(self._notify)
        self.hotkeys.apply(self.settings.hotkeys_enabled, self.settings.hotkey_map())

        self.overlay.show()
        self._sync_actions()

        if self.settings.first_run:
            self.settings.first_run = False
            save_settings(self.settings)
            self._notify("Colorblind Helper is running. Right-click the tray icon (or the "
                         "overlay when detached) for options.", "Colorblind Helper")
        if sys.platform == "darwin":
            self._mac_permission_hint()

    # ------------------------------------------------------------------ menu / tray
    def _build_menu(self) -> None:
        self.menu = QMenu()
        self.act_attach = QAction("Attach to cursor", self.menu, checkable=True)
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

        theme = QMenu("Theme", self.menu)
        self.act_theme_dark = QAction("Dark", theme, checkable=True)
        self.act_theme_light = QAction("Light", theme, checkable=True)
        self.act_theme_dark.triggered.connect(lambda: self.set_theme("dark"))
        self.act_theme_light.triggered.connect(lambda: self.set_theme("light"))
        theme.addAction(self.act_theme_dark)
        theme.addAction(self.act_theme_light)

        sims = StayOpenMenu("Colour-blind simulations", self.menu)
        self.sim_actions: dict[str, QAction] = {}
        for kind, label in CVD_LABELS.items():
            act = QAction(label, sims, checkable=True)
            act.triggered.connect(lambda checked, k=kind: self.set_simulation(k, checked))
            sims.addAction(act)
            self.sim_actions[kind] = act

        act_settings = QAction("Settings…", self.menu)
        act_settings.triggered.connect(self.open_settings)
        act_quit = QAction("Quit", self.menu)
        act_quit.triggered.connect(self.quit)

        m = self.menu
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
        m.addMenu(theme)
        m.addAction(act_settings)
        m.addSeparator()
        m.addAction(act_quit)

    def _sync_actions(self) -> None:
        s = self.settings
        for act, val in ((self.act_attach, s.attach_to_cursor),
                         (self.act_desc, s.descriptive_mode),
                         (self.act_freeze, self.overlay.frozen),
                         (self.act_visible, self.overlay.isVisible()),
                         (self.act_theme_dark, s.theme == "dark"),
                         (self.act_theme_light, s.theme == "light"),
                         *((a, getattr(s, f"sim_{k}")) for k, a in self.sim_actions.items())):
            act.blockSignals(True)
            act.setChecked(bool(val))
            act.blockSignals(False)
        has = self.overlay.info is not None
        self.act_copy_hex.setEnabled(has)
        self.act_copy_rgb.setEnabled(has)
        self.act_copy_desc.setEnabled(has)

    def _show_menu_at(self, pos: QPoint) -> None:
        self._sync_actions()
        self.menu.popup(pos)

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger and sys.platform != "darwin":
            self.set_visible(not self.overlay.isVisible())
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_settings()

    def _notify(self, text: str, title: str = "Colorblind Helper") -> None:
        if self.tray.isVisible() and QSystemTrayIcon.supportsMessages():
            self.tray.showMessage(title, text, make_icon(), 5000)
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

    def set_theme(self, theme: str) -> None:
        self.settings.theme = theme
        self._on_settings_changed()

    def copy_hex(self) -> None:
        info = self.overlay.info
        if info:
            text = info.hex(self.settings.uppercase_hex)
            self.qapp.clipboard().setText(text)
            self._notify(f"Copied {text}")

    def copy_rgb(self) -> None:
        info = self.overlay.info
        if info:
            text = "rgb({}, {}, {})".format(*info.rgb)
            self.qapp.clipboard().setText(text)
            self._notify(f"Copied {text}")

    def copy_description(self) -> None:
        info = self.overlay.info
        if info:
            text = f"{info.description} ({info.hex(self.settings.uppercase_hex)}, closest: {info.name})"
            self.qapp.clipboard().setText(text)
            self._notify(f"Copied: {text}")

    def open_settings(self) -> None:
        if self.dialog is None:
            self.dialog = SettingsDialog(self.settings, pynput_available())
            self.dialog.changed.connect(self._on_settings_changed)
        self.dialog.refresh()
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def quit(self) -> None:
        save_settings(self.settings)
        self.hotkeys.stop()
        self.tray.hide()
        self.qapp.quit()

    # ------------------------------------------------------------------ plumbing
    def _on_settings_changed(self) -> None:
        self.overlay.apply_settings()
        self.hotkeys.apply(self.settings.hotkeys_enabled, self.settings.hotkey_map())
        if self.dialog is not None and self.dialog.isVisible():
            self.dialog.refresh()
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
        return self.qapp.exec()


def main(argv: list[str] | None = None) -> int:
    app = ColorblindHelperApp(sys.argv if argv is None else argv)
    return app.run()
