"""A small website: upload two recordings, get a score and the notes and MIDI for each.

Run it with:
    .venv/bin/python app.py
then open http://127.0.0.1:8000
"""

import os
import secrets
import uuid
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename

from comparison import compare
from scoring import Settings, final_score
from timing import describe_tempo, measure_timing
from transcription import get_model, transcribe

ROOT = Path(__file__).resolve().parent
UPLOADS = ROOT / "uploads"  # one folder per job; ignored by git
UPLOADS.mkdir(exist_ok=True)

# Each recording the user uploads: form field name, label shown on the page.
RECORDINGS = [
    ("student", "Your recording"),
    ("reference", "Ideal pianist's recording"),
]


def secret_key() -> str:
    """Key that signs the settings cookie. Kept in a local file so it survives restarts."""
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    f = ROOT / ".flask_secret"
    if not f.exists():
        f.write_text(secrets.token_hex(32))
    return f.read_text().strip()


app = Flask(__name__)
app.secret_key = secret_key()
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB per request


def current_settings() -> Settings:
    """Settings live in the browser cookie until there are accounts."""
    return Settings.from_dict(session.get("settings", {}))


@app.get("/")
def index():
    return render_template("index.html", recordings=RECORDINGS, settings=current_settings())


@app.get("/settings")
def settings_page():
    return render_template("settings.html", s=current_settings())


@app.post("/settings")
def save_settings():
    form = request.form
    s = Settings.from_dict(
        {
            "include_notes": "include_notes" in form,
            "include_rhythm": "include_rhythm" in form,
            "include_tempo": "include_tempo" in form,
            "octave_ok": "octave_ok" in form,
            "rhythm_tolerance_ms": form.get("rhythm_tolerance_ms"),
            "min_loudness": form.get("min_loudness"),
        }
    )
    session["settings"] = s.to_dict()
    return redirect(url_for("index"))


@app.get("/settings/reset")
def reset_settings():
    session.pop("settings", None)
    return redirect(url_for("settings_page"))


@app.post("/transcribe")
def do_transcribe():
    s = current_settings()
    job = uuid.uuid4().hex[:8]
    folder = UPLOADS / job
    folder.mkdir()

    results = {}
    for field, label in RECORDINGS:
        upload = request.files.get(field)
        if upload is None or not upload.filename:
            abort(400, f"Please choose a file for: {label}")
        suffix = Path(secure_filename(upload.filename)).suffix.lower() or ".wav"
        audio_path = folder / f"{field}{suffix}"
        upload.save(audio_path)

        try:
            result = transcribe(audio_path, folder / f"{field}.mid")
        except Exception as exc:  # unreadable file, unsupported format, etc.
            abort(400, f"Could not transcribe {label} ({upload.filename}): {exc}")

        results[field] = {
            "label": label,
            "filename": upload.filename,
            "midi_url": f"/uploads/{job}/{field}.mid",
            "result": result,
        }

    comparison = compare(results["reference"]["result"].notes, results["student"]["result"].notes,
                         s.min_loudness, s.octave_ok)
    timing = measure_timing(comparison, s.rhythm_tolerance)
    score, parts, fell_back = final_score(comparison, timing, s)
    return render_template(
        "result.html",
        job=job,
        results=[results[f] for f, _ in RECORDINGS],
        comparison=comparison,
        timing=timing,
        tempo_text=describe_tempo(timing.tempo_percent),
        settings=s,
        score=score,
        parts=parts,
        fell_back=fell_back,
    )


@app.get("/uploads/<job>/<name>")
def download(job: str, name: str):
    return send_from_directory(UPLOADS / job, name, as_attachment=True)


if __name__ == "__main__":
    get_model()  # load once at startup so the first upload is not slow
    app.run(host="127.0.0.1", port=8000, debug=False)
