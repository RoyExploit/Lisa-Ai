"""
orb_stage.py
============

The particle orb, embedded INSIDE the Lisa AI main window.

This is a parented QWidget port of the same particle-sphere math used by
``ui_particle/particle_orb.py`` and ``hud_overlay.py``. It is designed as a
drop-in replacement for the old WebEngine/Three.js golden-orb background
inside ``BackgroundWidget``:

    stage = OrbStage(parent)
    stage.set_ai_state("listening")
    stage.set_audio_level(0.42)

States understood: idle / listening / thinking / speaking / executing /
processing / muted / error -- mapped onto the orb's idle / listening /
speaking visuals. Unknown states fall back to idle.
"""

from __future__ import annotations

import math
import random
import time

from PyQt6.QtCore import Qt, QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QRadialGradient
from PyQt6.QtWidgets import QWidget, QSizePolicy

STATE_COLORS = {
    "idle":      {"base": (70, 200, 180), "hot": (170, 255, 230)},
    "listening": {"base": (70, 140, 255), "hot": (150, 210, 255)},
    "speaking":  {"base": (200, 80, 220), "hot": (255, 170, 90)},
}

_APP_TO_ORB = {
    "idle": "idle", "ready": "idle", "muted": "idle", "error": "idle",
    "listening": "listening",
    "thinking": "speaking", "processing": "speaking",
    "executing": "speaking", "speaking": "speaking",
}

_N = 850


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

class OrbStage(QWidget):
    """Parented particle-sphere stage. Mirrors BackgroundWidget's feed API."""

    _state_sig = pyqtSignal(str)
    _audio_sig = pyqtSignal(float)

    def __init__(self, parent=None, num_particles=_N):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setAutoFillBackground(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        n = max(64, int(num_particles))
        self._dirs = _fibonacci_sphere(n)
        self._phase = [random.uniform(0, math.tau) for _ in range(n)]
        self._speed = [random.uniform(0.8, 2.4) for _ in range(n)]
        self._jit = [random.uniform(0.85, 1.15) for _ in range(n)]
        self._count = n

        self._state = "idle"
        self._amp = 0.0
        self._ext_amp = 0.0
        self._ext_at = 0.0
        self._level = 0.0
        self._level_at = 0.0
        self._angle = 0.0
        self._t0 = time.time()
        # Horizontal insets (px) the orb must stay inside so it never sits under
        # the left rail or the right chat sidebar. 0 = use the full widget.
        self._inset_left = 0
        self._inset_right = 0
        # 1.0 = full glow (dashboard); <1.0 fades the orb so content pages
        # (settings/home/devices) stay readable on top of it.
        self._dim = 1.0

        self._state_sig.connect(self._do_set_ai_state)
        self._audio_sig.connect(self._do_set_audio_level)

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._tick)
        self._tmr.start(16)

    # -- public feed API (same shape as BackgroundWidget) -------------------

    def set_ai_state(self, state: str) -> None:
        try:
            self._state_sig.emit(str(state or "idle"))
        except Exception:
            pass

    def set_stage_insets(self, left: int = 0, right: int = 0) -> None:
        """Constrain the orb to the visible stage between the left rail and the
        right chat sidebar so it never sits under a panel. 0 = no inset."""
        self._inset_left = max(0, int(left))
        self._inset_right = max(0, int(right))

    def set_dim(self, factor: float) -> None:
        """1.0 = full glow; <1.0 fades the orb so overlaying content stays
        readable. Clamped to [0.0, 1.0]."""
        self._dim = max(0.0, min(1.0, float(factor)))

    def set_audio_level(self, level: float) -> None:
        try:
            self._audio_sig.emit(float(level))
        except Exception:
            pass

    # -- slots (GUI thread) ---------------------------------------------------

    def _do_set_ai_state(self, state: str) -> None:
        mapped = _APP_TO_ORB.get((state or "idle").strip().lower(), "idle")
        self._state = mapped

    def _do_set_audio_level(self, level: float) -> None:
        self._level = max(0.0, min(1.0, float(level)))
        self._level_at = time.time()
        self._ext_amp = self._level
        self._ext_at = self._level_at

    # -- animation --------------------------------------------------------------

    def _target_amp(self, t: float) -> float:
        now = time.time()
        if self._state == "idle":
            return max(0.12 + 0.05 * math.sin(t * 0.9), 0.0)
        if self._state == "listening":
            if now - self._level_at < 0.6:
                return max(self._level, 0.08)
            return 0.25 + 0.25 * abs(math.sin(t * 2.3)) + 0.1 * random.random()
        if now - self._ext_at < 0.6:
            return self._ext_amp
        wave = 0.5 + 0.3 * math.sin(t * 6.0) + 0.2 * math.sin(t * 13.0 + 1.3)
        burst = 0.15 if random.random() < 0.08 else 0.0
        return max(0.0, min(1.0, wave + burst))

    def _tick(self) -> None:
        t = time.time() - self._t0
        self._amp += (self._target_amp(t) - self._amp) * 0.35
        self._angle += 0.006 + self._amp * 0.01
        self.update()

    # -- rendering ----------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        w = max(1, self.width())
        h = max(1, self.height())
        # Visible stage = the free area between the left rail and right sidebar.
        vis_l = min(self._inset_left, w - 1)
        vis_r = max(vis_l + 1, w - self._inset_right)
        vis_w = max(1, vis_r - vis_l)
        cx, cy = (vis_l + vis_r) / 2.0, h / 2.0
        r0 = min(vis_w, h) * 0.30
        dim = self._dim

        col = STATE_COLORS[self._state]
        base, hot = col["base"], col["hot"]

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        grad = QRadialGradient(QPointF(cx, cy), r0 * 1.6)
        alpha = int(255 * (0.06 + self._amp * 0.22) * dim)
        grad.setColorAt(0.0, QColor(base[0], base[1], base[2], alpha))
        grad.setColorAt(1.0, QColor(base[0], base[1], base[2], 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawRect(0, 0, w, h)

        t = time.time() - self._t0
        ca, sa = math.cos(self._angle), math.sin(self._angle)
        tilt = math.radians(18.0)
        ct, st = math.cos(tilt), math.sin(tilt)
        fov = 620.0 * min(vis_w, h) / 760.0

        pts = []
        for i in range(self._count):
            x, y, z = self._dirs[i]
            rad = r0 * self._jit[i] * (1.0 + self._amp * 0.55 * math.sin(t * self._speed[i] + self._phase[i]))
            xr = x * ca - z * sa
            zr = x * sa + z * ca
            yr = y * ct - zr * st
            z2 = y * st + zr * ct
            sc = fov / (fov + z2 * rad)
            pts.append((z2 * rad, cx + xr * rad * sc, cy + yr * rad * sc, rad, sc, i))
        pts.sort(key=lambda q: q[0])

        for z2rad, sx, sy, rad, sc, i in pts:
            depth = (z2rad + rad) / (2.0 * rad + 1e-6)
            e = min(1.0, self._amp * 1.6 * self._jit[i])
            c = _lerp(base, hot, e * (0.4 + 0.6 * depth))
            rp = 0.9 + 1.1 * sc
            p.setBrush(QColor(c[0], c[1], c[2], int(255 * dim)))
            p.drawEllipse(QPointF(sx, sy), rp, rp)

        p.end()
