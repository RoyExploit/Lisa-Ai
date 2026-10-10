# Lisa AI — Installer / Packaging

Two PyInstaller stages produce a single, fully self-contained setup file that
can be copied to any Windows PC and installed offline. Everything the app
needs at runtime (Python, all pip dependencies, PyQt6 + WebEngine, mediapipe,
OpenCV, model files, assets) is bundled — the target PC needs nothing
installed.

## Stage 1 — the app (`LisaAI.spec`)

```
.venv\Scripts\pyinstaller.exe --noconfirm installer\LisaAI.spec
```

Output: `dist\LisaAI\` (folder) with `LisaAI.exe` + all bundled
dependencies. The spec bundles `assets/`, `config/`, `core/`, `actions/`,
`lisa_connect/`, `dashboard/static/`, `smart_home/`, `memory/`, `plugins/`,
`features/`.

**Personal-data exclusions** (never shipped to other people):
`api_keys.json`, `identity.json`, `app_settings.json`, `lisa_connect.json`,
`devices.json`, `ig_session.json`, `email_credentials.json`,
`learned_rules.json`, location/history caches, and the whole `user_data/`
tree.

## Stage 2 — the setup program (`LisaAI_Setup.spec`)

```
.venv\Scripts\pyinstaller.exe --noconfirm installer\LisaAI_Setup.spec
```

Output: `dist\LisaAI_Setup.exe` — a single file containing the entire
Stage-1 app payload (`LisaAI/` folder) plus the PyQt6 install wizard
(`install_wizard.py`). On the target PC it: unpacks to a temp folder, copies
`LisaAI/` to the chosen install location (default `C:\Program Files\Lisa AI`
or user-selected), creates Desktop + Start-menu shortcuts named
"Lisa AI", and offers a Launch button.

## What the end user needs

- Windows 10/11 (x64).
- Internet only for the AI itself (Gemini API / Google speech / updates);
  installation is fully offline.
- First launch asks no dependency setup — everything is inside.

## Rebuild checklist

1. `.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller pywin32`
2. Stage 1, then Stage 2 (above).
3. Copy `dist\LisaAI_Setup.exe` to the target machine and run it.
