# PaddleOCR Studio

Live demo: https://ocr-k7fv.onrender.com/

A minimal, browser-first front-end for running PaddleOCR inference locally or on Render. This repository contains a small Flask app (`local_server`) that accepts image uploads, runs OCR with PaddleOCR, and returns annotated previews + JSON artifacts.

Quick local run (Windows PowerShell):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r PaddleOCR-main/requirements.txt
python local_server/app.py
# Open http://127.0.0.1:5000/
```

Render notes
- `render.yaml` and a `Dockerfile` are included for one-click deploy on Render.
- If you redeploy on Render, use **Clear build cache & deploy** to ensure the new Docker build is used.
- Cold starts: PaddleOCR downloads model files on first use; expect the first request to take extra time. The app exposes `/healthz` for readiness checks.

Project layout (useful files)
- `local_server/` — Flask app, templates, static assets
- `run_ocr_demo.py` — CLI demo runner
- `run_ocr_demo.ps1` — PowerShell demo launcher
- `render.yaml`, `Dockerfile` — deploy manifests

Credits
- This project bundles and integrates the PaddleOCR toolkit. See `PaddleOCR-main/README.md` for the upstream project documentation and licensing.

If you want, I can add a short banner page or README content directly to the live site homepage. Tell me what text or links you want shown.
