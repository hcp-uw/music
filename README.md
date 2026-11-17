# music

A practice tool for musicians. Record yourself playing a piece, compare it to a reference recording, and see exactly where your take differs.

Read [PLAN.md](PLAN.md) for the core requirements and post-MVP features.

## Setup

Needs Python 3.10 or newer. On a Mac, non-WAV recordings are converted with the built-in `afconvert`; elsewhere install `ffmpeg`.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run the website

```bash
.venv/bin/python app.py
```

Then open <http://127.0.0.1:8000>. Upload your recording and the ideal pianist's recording. You get a note-by-note score (correct, wrong octave, wrong, missed, extra) plus the notes and a MIDI file for each. Uploaded files and results land in `uploads/`, which git ignores.

## Transcribe one file from the command line

```bash
.venv/bin/python scripts/transcribe.py path/to/recording.m4a
```

Prints every note found and writes a `.mid` file next to the recording.

## Compare two recordings from the command line

```bash
.venv/bin/python scripts/compare.py reference.m4a student.m4a
```

Prints the score, the counts, and a note-by-note breakdown. `--min-loudness` and `--strict-octave` match the website settings.

## Tests

```bash
.venv/bin/python -m unittest
```

## Layout

- `transcription.py` turns a recording into notes and a MIDI file with Basic Pitch. Everything else calls this.
- `comparison.py` lines up two note lists and scores them. Timing is ignored for now; notes starting together are treated as a chord.
- `app.py` and `templates/` are the website.
- `scripts/transcribe.py` and `scripts/compare.py` are the command line versions.
- `tests/` has unit tests for silence trimming and the comparison.
