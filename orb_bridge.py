"""
orb_bridge.py
=============

Bridges the Lisa AI assistant state machine to the orb UIs:

  * External HUD  -- ``hud_overlay.HudOverlay`` (native PyQt6 overlay)

The embedded particle stage (``orb_stage.OrbStage``) lives inside the main
window and is fed separately by ``BackgroundWidget``. This bridge only manages
the transparent external overlay, driven by direct method calls. There is **no
localhost server, no Electron and no NPM** involved, so everything bundles into
a single PyInstaller EXE and works fully offline.

The assistant exposes states like ``idle``, ``listening``, ``thinking``,
``speaking``, ``executing``... The orb only understands three visual states
(``idle`` / ``listening`` / ``speaking``), so this module maps the rich app
state onto that smaller set and forwards it to the overlay.

Everything here is best-effort and must never raise: if the HUD overlay is
unavailable, the assistant keeps running normally without it.

Usage (already wired into ``ui.LisaUI.set_state``)::

    import orb_bridge
    orb_bridge.start()            # lazily bring up the HUD overlay
    orb_bridge.set_state("speaking")
    orb_bridge.feed_amplitude(0.6)   # 0..1 while TTS plays
    orb_bridge.show_hud()         # on minimize
    orb_bridge.hide_hud()         # on restore
    orb_bridge.stop()
"""

from __future__ import annotations

import os
import threading

# --- Feature toggles (env-overridable) --------------------------------------
# The overlay is on by default; set LISA_ORBS=0 or LISA_HUD_ORB=0 to disable.
_ORBS_ENABLED = os.environ.get("LISA_ORBS", "1") != "0"
_HUD_ORB_ENABLED = os.environ.get("LISA_HUD_ORB", "1") != "0"

# App state -> orb visual state ("idle" | "listening" | "speaking").
_STATE_MAP = {
    "idle": "idle",
    "ready": "idle",
    "muted": "idle",
    "error": "idle",
    "listening": "listening",
    "thinking": "speaking",
    "processing": "speaking",
    "executing": "speaking",
    "speaking": "speaking",
}

_lock = threading.Lock()
_hud = None            # HudOverlay instance (native external overlay)
_started = False
_last_state = "idle"


def _map_state(state: str) -> str:
    return _STATE_MAP.get((state or "idle").strip().lower(), "idle")


def start() -> None:
    """Bring up the HUD overlay. Safe to call multiple times."""
    global _hud, _started
    if not _ORBS_ENABLED:
        return
    with _lock:
        if _started:
            return
        _started = True

    if _HUD_ORB_ENABLED:
        try:
            from PyQt6.QtWidgets import QApplication
            from hud_overlay import HudOverlay

            if QApplication.instance() is not None:
                _hud = HudOverlay()
                # Stay hidden while the main window is open; shown only
                # on minimize via show_hud().
            else:
                print("[OrbBridge] HUD overlay skipped: no QApplication running.")
        except Exception as exc:
            print(f"[OrbBridge] Native HUD overlay unavailable: {exc}")
            _hud = None


def show_hud() -> None:
    """Show the transparent HUD overlay (called on minimize)."""
    if not _ORBS_ENABLED or not _HUD_ORB_ENABLED:
        return
    if _hud is not None:
        try:
            _hud.show()
            _hud.raise_()
        except Exception:
            pass


def hide_hud() -> None:
    """Hide the transparent HUD overlay (called when main window restores)."""
    if _hud is not None:
        try:
            _hud.hide()
        except Exception:
            pass


def is_hud_visible() -> bool:
    if _hud is None:
        return False
    try:
        return bool(_hud.isVisible())
    except Exception:
        return False


def set_state(state: str) -> None:
    """Forward an assistant state change to the HUD overlay."""
    if not _ORBS_ENABLED:
        return
    global _last_state
    mapped = _map_state(state)

    if _hud is not None:
        try:
            _hud.set_state(mapped)
        except Exception:
            pass

    _last_state = mapped


def feed_amplitude(level: float) -> None:
    """Feed a 0..1 TTS volume level to the HUD overlay."""
    if not _ORBS_ENABLED:
        return
    lvl = max(0.0, min(1.0, float(level)))
    if _hud is not None:
        try:
            _hud.feed_amplitude(lvl)
        except Exception:
            pass


def stop() -> None:
    """Shut down the HUD overlay."""
    global _hud, _started
    if _hud is not None:
        try:
            _hud.shutdown()
        except Exception:
            pass
        _hud = None
    _started = False
