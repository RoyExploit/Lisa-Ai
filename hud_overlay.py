"""
hud_overlay.py
==============

A native PyQt6 replacement for the Electron ``HUD_orb``.

Renders the same reactive particle orb as a small, transparent, always-on-top,
draggable overlay that lives *inside* the Lisa AI process. Because it is driven
by direct method calls (``set_state`` / ``feed_amplitude``) instead of a
localhost HTTP socket, there is **no server, no Electron, no NPM and no second
process** -- so it bundles cleanly into a single PyInstaller EXE and works
fully offline.

Visual behaviour mirrors the original ``hud_orb/renderer/index.html``:
  * idle       -> gentle breathing, orb small and dim
  * listening  -> simulated mic pulse, orb scales up
  * speaking   -> energetic jump driven by real TTS amplitude when provided
"""

from __future__ import annotations

import math
import random
import time

from PyQt6.QtCore import Qt, QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QGuiApplication, QAction
from PyQt6.QtWidgets import QWidget, QMenu, QApplication

# Same palette as particle_orb.py / hud_orb.
STATE_COLORS = {
    "idle":      {"base": (70, 200, 180), "hot": (170, 255, 230)},
    "listening": {"base": (70, 140, 255), "hot": (150, 210, 255)},
    "speaking":  {"base": (200, 80, 220), "hot": (255, 170, 90)},
}

_N = 520          # particle count (matches the JS renderer)
_SIZE = 180       # widget edge length in px
_FPS = 16         # ~60 fps tick


def _fibonacci_sphere(n):
    pts = []
    golden = math.pi * (3.0 - math.sqrt(5.0))
    for i in range(n):
        y = 1.0 - (i / float(n - 1)) * 2.0
        r = math.sqrt(max(0.0, 1.0 - y * y))
        th = golden * i
        pts.append((math.cos(th) * r, y, math.sin(th) * r))
    return pts


def _lerp(a, b, f):
    f = max(0.0, min(1.0, f))
    return tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3))


class HudOverlay(QWidget):
    """Transparent, always-on-top, draggable particle orb (no server)."""

    # Signals make updates thread-safe: emitting from any thread queues the
    # slot onto the GUI thread where the widget lives.
    _state_sig = pyqtSignal(str)
    _amp_sig = pyqtSignal(float)
    # Right-click menu actions (Open App, Chat, Voice, Settings, Hide, Quit).
    action_requested = pyqtSignal(str)

    def __init__(self, size=_SIZE):
        super().__init__(None, Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(size, size)

        # Precompute the point cloud once.
        self._dirs = _fibonacci_sphere(_N)
        self._phase = [random.uniform(0, math.tau) for _ in range(_N)]
        self._speed = [random.uniform(0.8, 2.4) for _ in range(_N)]
        self._jit = [random.uniform(0.85, 1.15) for _ in range(_N)]

        self._state = "idle"
        self._amp = 0.0
        self._ext_amp = 0.0
        self._ext_at = 0.0
        self._angle = 0.0
        self._scale = 0.62
        self._active_until = 0.0
        self._t0 = time.time()
        self._drag_pos = None

        self._state_sig.connect(self._on_state)
        self._amp_sig.connect(self._on_amp)

        self._place_top_right()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(_FPS)

    # -- public control API (safe from any thread) ------------------------

    def set_state(self, state: str) -> None:
        self._state_sig.emit((state or "idle").strip().lower())

    def feed_amplitude(self, level: float) -> None:
        self._amp_sig.emit(float(level))

    def shutdown(self) -> None:
        try:
            self._timer.stop()
            self.close()
        except Exception:
            pass

    # -- slots (GUI thread) ------------------------------------------------

    def _on_state(self, state: str) -> None:
        self._state = state if state in STATE_COLORS else "idle"

    def _on_amp(self, level: float) -> None:
        self._ext_amp = max(0.0, min(1.0, level))
        self._ext_at = time.time()

    # -- layout ------------------------------------------------------------

    def _place_top_right(self) -> None:
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return
        wa = screen.availableGeometry()
        margin = 24
        self.move(wa.x() + wa.width() - self.width() - margin, wa.y() + margin)

    # -- animation ---------------------------------------------------------

    def _target_amp(self, t):
        now = time.time()
        if self._state == "idle":
            return max(0.12 + 0.05 * math.sin(t * 0.9), 0.0)
        if self._state == "listening":
            return 0.25 + 0.25 * abs(math.sin(t * 2.3)) + 0.1 * random.random()
        # speaking
        if now - self._ext_at < 0.6:
            return self._ext_amp
        wave = 0.5 + 0.3 * math.sin(t * 6.0) + 0.2 * math.sin(t * 13.0 + 1.3)
        burst = 0.15 if random.random() < 0.08 else 0.0
        return max(0.0, min(1.0, wave + burst))

    def _tick(self) -> None:
        t = time.time() - self._t0
        self._amp += (self._target_amp(t) - self._amp) * 0.35
        if self._state != "idle" or self._amp > 0.25:
            self._active_until = time.time() + 0.7
        self._angle += 0.006 + self._amp * 0.01
        self.update()

    # -- rendering ---------------------------------------------------------

    def paintEvent(self, _event) -> None:
        s = self.width()
        cx = cy = s / 2.0

        target_scale = 1.0 if time.time() < self._active_until else 0.62
        self._scale += (target_scale - self._scale) * 0.12

        col = STATE_COLORS[self._state]
        base, hot = col["base"], col["hot"]
        r0 = s * 0.30 * self._scale

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Radial glow behind the orb (rest of the widget stays transparent).
        grad = QRadialGradient(QPointF(cx, cy), r0)
        alpha = int(255 * (0.06 + self._amp * 0.22))
        grad.setColorAt(0.0, QColor(base[0], base[1], base[2], alpha))
        grad.setColorAt(1.0, QColor(base[0], base[1], base[2], 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawRect(0, 0, s, s)

        ca, sa = math.cos(self._angle), math.sin(self._angle)
        tilt = math.radians(18.0)
        ct, st = math.cos(tilt), math.sin(tilt)
        fov = 620.0 * s / 760.0
        t = time.time() - self._t0

        pts = []
        for i, (x, y, z) in enumerate(self._dirs):
            rad = r0 * self._jit[i] * (1.0 + self._amp * 0.55 * math.sin(t * self._speed[i] + self._phase[i]))
            xr = x * ca - z * sa
            zr = x * sa + z * ca
            yr = y * ct - zr * st
            z2 = y * st + zr * ct
            sc = fov / (fov + z2 * rad)
            sx = cx + xr * rad * sc
            sy = cy + yr * rad * sc
            pts.append((z2 * rad, sx, sy, rad, sc, i))
        pts.sort(key=lambda q: q[0])

        for z2rad, sx, sy, rad, sc, i in pts:
            depth = (z2rad + rad) / (2.0 * rad + 1e-6)
            e = min(1.0, self._amp * 1.6 * self._jit[i])
            c = _lerp(base, hot, e * (0.4 + 0.6 * depth))
            rp = 0.7 + 0.9 * sc
            p.setBrush(QColor(c[0], c[1], c[2]))
            p.drawEllipse(QPointF(sx, sy), rp, rp)

        p.end()

    # -- dragging ----------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        event.accept()

    # -- right-click options menu ------------------------------------------

    def contextMenuEvent(self, event) -> None:
        """Show the same options the floating launcher offered, so the single
        HUD orb fully replaces the old second floating icon."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #0c1220;
                color: #e6f7ff;
                border: 1px solid rgba(0, 229, 255, 0.35);
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 7px 22px 7px 16px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background: rgba(0, 229, 255, 0.20);
                color: #00e5ff;
            }
            QMenu::separator {
                height: 1px;
                background: rgba(255, 255, 255, 0.10);
                margin: 4px 6px;
            }
        """)

        open_full = QAction("Open Lisa AI (Full App)", self)
        open_full.triggered.connect(lambda: self.action_requested.emit("open_app"))
        menu.addAction(open_full)

        open_ws = QAction("Open Chat Workspace", self)
        open_ws.triggered.connect(lambda: self.action_requested.emit("open_workspace"))
        menu.addAction(open_ws)

        menu.addSeparator()

        voice_mode = QAction("Toggle Voice Mode", self)
        voice_mode.triggered.connect(lambda: self.action_requested.emit("voice_mode"))
        menu.addAction(voice_mode)

        settings_act = QAction("Settings", self)
        settings_act.triggered.connect(lambda: self.action_requested.emit("settings"))
        menu.addAction(settings_act)

        menu.addSeparator()

        # Wake on voice / assistant-name (listen even while sleeping/muted).
        wake_act = QAction("Wake on Voice / Name", self)
        wake_act.setCheckable(True)
        try:
            from memory import config_manager

            wake_act.setChecked(bool(config_manager.get_wake_word_enabled()))
        except Exception:
            wake_act.setChecked(True)
        wake_act.triggered.connect(
            lambda checked: self.action_requested.emit("toggle_wake_word")
        )
        menu.addAction(wake_act)

        # Launch Lisa automatically when Windows starts.
        autostart_act = QAction("Start with Windows", self)
        autostart_act.setCheckable(True)
        try:
            from core import autostart

            autostart_act.setChecked(bool(autostart.is_enabled()))
        except Exception:
            autostart_act.setChecked(False)
        autostart_act.triggered.connect(
            lambda checked: self.action_requested.emit("toggle_autostart")
        )
        menu.addAction(autostart_act)

        menu.addSeparator()

        hide_act = QAction("Hide HUD Orb", self)
        hide_act.triggered.connect(lambda: self.action_requested.emit("hide_hud"))
        menu.addAction(hide_act)

        quit_act = QAction("Quit Lisa", self)
        quit_act.triggered.connect(lambda: self.action_requested.emit("quit"))
        menu.addAction(quit_act)

        menu.exec(event.globalPos())
