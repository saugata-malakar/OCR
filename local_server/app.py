from __future__ import annotations

import io
import json
import os
import threading
from collections.abc import Iterable
from contextlib import redirect_stdout
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, send_from_directory, url_for
from paddleocr import PaddleOCR
from werkzeug.utils import secure_filename


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "local_server_output"
UPLOAD_DIR = OUTPUT_DIR / "uploads"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "bmp", "webp"}

app = Flask(__name__, template_folder="templates", static_folder="static")
_ocr_lock = threading.Lock()
_ocr: PaddleOCR | None = None
_warmup_started = False


def _get_ocr() -> PaddleOCR:
    global _ocr
    if _ocr is None:
        with _ocr_lock:
            if _ocr is None:
                _ocr = PaddleOCR(engine=os.getenv("OCR_ENGINE", "paddle"))
    return _ocr


def _warmup_ocr() -> None:
    try:
        _get_ocr()
    except Exception:
        # Warmup is best-effort; the first real OCR request will surface any error.
        pass


def _start_warmup() -> None:
    global _warmup_started
    if _warmup_started:
        return
    _warmup_started = True
    threading.Thread(target=_warmup_ocr, daemon=True).start()


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _collect_result_texts(result_dir: Path) -> list[str]:
    texts: list[str] = []
    for json_path in sorted(result_dir.glob("*.json")):
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        texts.extend(payload.get("rec_texts", []))
    return texts


def _collect_result_scores(result_dir: Path) -> list[float]:
    scores: list[float] = []
    for json_path in sorted(result_dir.glob("*.json")):
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        scores.extend(payload.get("rec_scores", []))
    return scores


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


@app.route("/uploads/<path:filename>")
def uploads(filename: str):
    return send_from_directory(UPLOAD_DIR.as_posix(), filename)


@app.route("/", methods=["GET", "POST"])
def index():
    result_texts: list[str] | None = None
    annotated_relpath: str | None = None
    result_summary: str | None = None
    source_path: str | None = None
    output_files: list[str] = []
    stats = {"text_count": 0, "artifact_count": 0, "avg_score": None}
    if request.method == "POST":
        if "image" not in request.files:
            return redirect(request.url)
        file = request.files["image"]
        if file.filename == "":
            return redirect(request.url)
        if not _allowed_file(file.filename):
            abort(400, description="Unsupported file type")

        filename = secure_filename(file.filename)
        if not filename:
            abort(400, description="Invalid file name")

        save_path = UPLOAD_DIR / filename
        file.save(save_path)
        source_path = f"uploads/{filename}"

        # Run OCR and capture the printed summary from the PaddleOCR result object.
        result = _get_ocr().predict(str(save_path))

        summary_buffer = io.StringIO()
        for item in result:
            if hasattr(item, "print"):
                with redirect_stdout(summary_buffer):
                    item.print()

        # Save annotated image(s) into a folder per upload
        out_folder = UPLOAD_DIR / f"{filename}_out"
        out_folder.mkdir(parents=True, exist_ok=True)
        for idx, item in enumerate(result, start=1):
            if hasattr(item, "save_to_img"):
                item.save_to_img(str(out_folder))
            if hasattr(item, "save_to_json"):
                json_path = out_folder / f"result_{idx}.json"
                item.save_to_json(str(json_path))
        texts = _collect_result_texts(out_folder)
        scores = _collect_result_scores(out_folder)
        # Use first saved PNG if available
        annotated_files = list(out_folder.glob("**/*.png"))
        if annotated_files:
            annotated_relpath = f"uploads/{filename}_out/{annotated_files[0].name}"
        output_files = [f"uploads/{filename}_out/{path.name}" for path in sorted(out_folder.glob("*.json"))]

        result_texts = texts
        result_summary = summary_buffer.getvalue().strip() or "OCR completed, but no printed summary was captured."
        stats = {
            "text_count": len(texts),
            "artifact_count": len(output_files),
            "avg_score": round(sum(scores) / len(scores), 3) if scores else None,
        }

    return render_template(
        "index.html",
        result_texts=result_texts,
        result_summary=result_summary,
        annotated_relpath=annotated_relpath,
        source_path=source_path,
        output_files=output_files,
        stats=stats,
    )


@app.before_request
def _ensure_warmup_started() -> None:
    # Start model initialization in the background so the service stays responsive.
    if request.method == "GET":
        _start_warmup()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
