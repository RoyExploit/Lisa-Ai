# Local ONNX wake-word engine (offline, on-device).
#
# Install (Python <= 3.13): just `pip install -r requirements.txt`.
# Install (Python 3.14, where openwakeword's librosa/numba chain has no wheels):
#   pip install onnxruntime tqdm
#   pip install openwakeword --no-deps
#   python -c "from openwakeword.utils import download_models; download_models(model_names=['hey_jarvis_v0.1'])"
#
# Custom wake word for YOUR assistant name: train an ONNX model with the
# openWakeWord training pipeline and drop it in `assets/wakeword/` named after
# the assistant (e.g. `lisa.onnx`, `hey_alex.onnx`). It is picked up on the
# next launch automatically — no code changes required.