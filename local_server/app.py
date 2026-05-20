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
from uuid import uuid4
from datetime import datetime
from typing import Dict, Any


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "local_server_output"
UPLOAD_DIR = OUTPUT_DIR / "uploads"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
JOB_DIR = OUTPUT_DIR / "jobs"
JOB_DIR.mkdir(parents=True, exist_ok=True)

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


def _write_status(job_dir: Path, data: Dict[str, Any]) -> None:
    (job_dir / "status.json").write_text(json.dumps(data), encoding="utf-8")


def _read_status(job_dir: Path) -> Dict[str, Any]:
    p = job_dir / "status.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


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


@app.route('/job_files/<job_id>/<path:filename>')
def job_files(job_id: str, filename: str):
    job_dir = JOB_DIR / job_id
    if not job_dir.exists():
        abort(404)
    return send_from_directory(job_dir.as_posix(), filename)


@app.route('/status/<job_id>')
def job_status(job_id: str):
    job_dir = JOB_DIR / job_id
    if not job_dir.exists():
        return {"status": "not_found"}, 404
    return _read_status(job_dir)


@app.route('/result/<job_id>')
def job_result(job_id: str):
    job_dir = JOB_DIR / job_id
    if not job_dir.exists():
        return {"status": "not_found"}, 404
    status = _read_status(job_dir)
    if status.get('status') != 'done':
        return status, 202
    # Build result payload
    results = {
        'status': 'done',
        'result_texts': status.get('result_texts', []),
        'result_summary': status.get('result_summary'),
        'annotated_url': url_for('job_files', job_id=job_id, filename=status.get('annotated_file')) if status.get('annotated_file') else None,
        'output_files': [url_for('job_files', job_id=job_id, filename=p) for p in status.get('output_files', [])],
    }
    return results


def _process_job(job_id: str, save_path: Path, filename: str) -> None:
    job_dir = JOB_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    _write_status(job_dir, {"status": "running", "created_at": datetime.utcnow().isoformat()})
    try:
        result = _get_ocr().predict(str(save_path))

        summary_buffer = io.StringIO()
        for item in result:
            if hasattr(item, "print"):
                with redirect_stdout(summary_buffer):
                    item.print()

        output_files: list[str] = []
        annotated_file: str | None = None
        for idx, item in enumerate(result, start=1):
            if hasattr(item, "save_to_img"):
                item.save_to_img(str(job_dir))
            if hasattr(item, "save_to_json"):
                json_path = job_dir / f"result_{idx}.json"
                item.save_to_json(str(json_path))
                output_files.append(json_path.name)

        texts = _collect_result_texts(job_dir)
        scores = _collect_result_scores(job_dir)
        annotated_files = list(job_dir.glob("**/*.png"))
        if annotated_files:
            annotated_file = annotated_files[0].name

        status_payload = {
            "status": "done",
            "created_at": datetime.utcnow().isoformat(),
            "result_texts": texts,
            "result_summary": summary_buffer.getvalue().strip(),
            "output_files": output_files,
            "annotated_file": annotated_file,
            "avg_score": round(sum(scores) / len(scores), 3) if scores else None,
        }
        _write_status(job_dir, status_payload)
    except Exception as e:
        _write_status(job_dir, {"status": "failed", "error": str(e)})


@app.route('/upload_async', methods=['POST'])
def upload_async():
    if 'image' not in request.files:
        return {"error": "no file"}, 400
    file = request.files['image']
    if file.filename == '':
        return {"error": "empty filename"}, 400
    if not _allowed_file(file.filename):
        return {"error": "unsupported file type"}, 400

    filename = secure_filename(file.filename)
    save_path = UPLOAD_DIR / filename
    file.save(save_path)

    job_id = uuid4().hex
    job_dir = JOB_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    _write_status(job_dir, {"status": "pending", "created_at": datetime.utcnow().isoformat()})

    threading.Thread(target=_process_job, args=(job_id, save_path, filename), daemon=True).start()

    return (
        {
            "job_id": job_id,
            "status_url": url_for('job_status', job_id=job_id, _external=True),
            "result_url": url_for('job_result', job_id=job_id, _external=True),
        },
        202,
    )


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
