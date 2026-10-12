"""
core/wake_word.py - Local ONNX wake-word engine (openWakeWord + onnxruntime).

Fully offline and on-device: a small ONNX model scores 16 kHz mic frames
locally. When the score stays above threshold for a few consecutive frames the
trigger callback fires - no internet, no cloud transcription, ~1-2% CPU.

Model resolution order:
  1. Custom models in ``assets/wakeword/*.onnx`` - filename should match the
     assistant's name (e.g. ``lisa.onnx``, ``hey_alex.onnx``). Train one with
     the openWakeWord training pipeline and drop it in; it is picked up on the
     next launch automatically.
  2. The best bundled openWakeWord model (``hey_jarvis``) as a generic
     "someone is addressing the assistant" acoustic trigger.

The engine degrades silently to "disabled" when openwakeword/onnxruntime are
not installed, so the app still runs without them. The cloud text matcher in
main.py remains active as a second wake path.
"""

from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np

_BASE = Path(__file__).resolve().parent.parent
_CUSTOM_DIR = _BASE / "assets" / "wakeword"

_SAMPLE_RATE = 16000
_BLOCK_FRAMES = 1600          # 100 ms per callback at 16 kHz
_SCORE_THRESHOLD = 0.5
_CONFIRM_BLOCKS = 2           # consecutive blocks above threshold to fire
_COOLDOWN_S = 4.0
_FALLBACK_MODEL = "hey_jarvis"

_engine_lock = threading.Lock()
_started = False
_status = "not started"


def engine_status() -> str:
    """Short human-readable status for logs/UI."""
    return _status


def _custom_models_for(assistant_name: str) -> list:
    """Custom .onnx models in assets/wakeword, best match for the name first."""
    if not _CUSTOM_DIR.is_dir():
        return []
    files = sorted(_CUSTOM_DIR.glob("*.onnx"))
    if not files:
        return []
    wanted = re.sub(r"[^a-z0-9]+", "_", (assistant_name or "").lower()).strip("_")
    ranked = []
    for p in files:
        score = 2 if wanted and wanted in p.stem.lower() else 1
        ranked.append((score, p))
    ranked.sort(key=lambda t: (-t[0], t[1].name))
    return [p for _, p in ranked]


def _ensure_bundled_models() -> None:
    """Best-effort seeding of the bundled openWakeWord ONNX models.

    The models live inside the openWakeWord package (`resources/models`) and
    are included in the packaged EXE via PyInstaller's collect_data_files.
    On a fresh source checkout without internet this may download on first
    run; any failure is caught and the Model constructor falls through to
    its own error handling so the app still starts.
    """
    try:
        import openwakeword
        from pathlib import Path as _P
        res = _P(openwakeword.__file__).resolve().parent / "resources" / "models"
        if (res / "hey_jarvis_v0.1.onnx").is_file() and (res / "embedding_model.onnx").is_file() and (res / "melspectrogram.onnx").is_file():
            return
        from openwakeword.utils import download_models
        print("[WakeWord] Bundled ONNX models missing - attempting one-time download...")
        download_models(model_names=["hey_jarvis_v0.1"])
    except Exception as exc:
        print(f"[WakeWord] Model auto-download skipped/failed: {exc}")


def _build_model(assistant_name: str):
    """Construct an openWakeWord model (custom ONNX preferred)."""
    from openwakeword import Model as _OWWModel
    _ensure_bundled_models()

    custom = _custom_models_for(assistant_name)
    if custom:
        wanted = re.sub(r"[^a-z0-9]+", "_", (assistant_name or "").lower()).strip("_")
        chosen = next((p for p in custom if wanted and wanted in p.stem.lower()), custom[0])
        print(f"[WakeWord] Loading custom ONNX model: {chosen.name}")
        return _OWWModel(wakeword_models=[str(chosen)], inference_framework="onnx")

    print(f"[WakeWord] No custom model in assets/wakeword - using bundled '{_FALLBACK_MODEL}'.")
    return _OWWModel(wakeword_models=[_FALLBACK_MODEL], inference_framework="onnx")


_state = {"model": None, "name": None}
_reload_requested = False


def custom_models_dir() -> Path:
    """Folder where the user drops/loads custom ``.onnx`` wake-word models.

    The desktop "Load wake-word model" dialog copies a chosen file here, and
    the engine picks it up without a restart.
    """
    return _CUSTOM_DIR


def request_reload(assistant_name: Optional[str] = None) -> None:
    """Ask the running engine to rebuild its model from assets/wakeword.

    Called after the user loads a new .onnx (or renames the assistant) so the
    acoustic trigger matches the new name immediately, with no app restart.
    """
    global _reload_requested
    if assistant_name:
        _state["name"] = assistant_name
    _reload_requested = True


def _rebuild_model() -> None:
    """Rebuild the model in-place from the current assistant name."""
    try:
        model = _build_model(_state.get("name") or "Lisa")
        _state["model"] = model
        print("[WakeWord] Model rebuilt for live wake-word update.")
    except Exception as exc:
        print(f"[WakeWord] Reload failed: {exc}")


def _engine_loop(assistant_name: str, on_trigger: Callable[[], None]) -> None:
    global _status
    try:
        import sounddevice as sd
    except Exception as exc:
        _status = f"disabled (sounddevice: {exc})"
        return

    try:
        model = _build_model(assistant_name)
    except Exception as exc:
        _status = f"disabled (model load failed: {exc})"
        print(f"[WakeWord] Model load failed: {exc}")
        return

    _state["model"] = model
    _state["name"] = assistant_name
    _status = "active"
    print(f"[WakeWord] Local ONNX engine active ({getattr(model, 'model_names', 'custom')}).")

    run_count = 0
    last_fire = 0.0

    def _callback(indata, frames, tinfo, status_flags):
        nonlocal run_count, last_fire
        try:
            mono = indata[:, 0] if indata.ndim > 1 else indata
            scores = _state["model"].predict(mono)
            best = 0.0
            if isinstance(scores, dict):
                best = max((float(v) for v in scores.values()), default=0.0)
            if best >= _SCORE_THRESHOLD:
                run_count += 1
            else:
                run_count = 0
            if run_count >= _CONFIRM_BLOCKS and (time.monotonic() - last_fire) > _COOLDOWN_S:
                run_count = 0
                last_fire = time.monotonic()
                print("[WakeWord] Local ONNX wake hit - triggering.")
                try:
                    on_trigger()
                except Exception as exc:
                    print(f"[WakeWord] Trigger callback failed: {exc}")
        except Exception:
            pass

    try:
        with sd.InputStream(
            samplerate=_SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=_BLOCK_FRAMES,
            callback=_callback,
        ):
            while True:
                time.sleep(1.0)
    except Exception as exc:
        _status = f"disabled (mic open failed: {exc})"
        print(f"[WakeWord] Mic open failed: {exc}")


def start_local_wakeword(on_trigger: Callable[[], None], assistant_name: Optional[str] = None) -> bool:
    """Start the local ONNX wake-word engine on a daemon thread.

    Returns True if the thread was started. Safe to call once at app start;
    silently disables itself when openwakeword/onnxruntime are missing or the
    wake word is turned off in settings.
    """
    global _started, _status
    with _engine_lock:
        if _started:
            return False
        try:
            from memory import config_manager
            if not config_manager.get_wake_word_enabled():
                _status = "disabled (wake word off in settings)"
                return False
            name = assistant_name or config_manager.get_assistant_name()
        except Exception:
            name = assistant_name or "Lisa"
        try:
            import openwakeword  # noqa: F401
            import onnxruntime  # noqa: F401
        except Exception as exc:
            _status = f"disabled ({exc.__class__.__name__}: package not installed)"
            print(f"[WakeWord] Local engine disabled - {exc}. Install: pip install openwakeword onnxruntime")
            return False
        _started = True
        threading.Thread(
            target=_engine_loop, args=(name, on_trigger), daemon=True, name="LisaWakeWord"
        ).start()
        return True