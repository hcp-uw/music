"""Compare a student's recording to a reference recording, note by note.

Usage:
    .venv/bin/python scripts/compare.py reference.m4a student.m4a [--min-loudness 0.3] [--strict-octave]

Both recordings are transcribed with Basic Pitch first (silence trimmed), then the
note lists are lined up and scored. See comparison.py for what the labels mean.
"""

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from comparison import compare  # noqa: E402
from scoring import Settings, final_score  # noqa: E402
from timing import describe_tempo, measure_timing  # noqa: E402
from transcription import transcribe  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reference", type=Path)
    ap.add_argument("student", type=Path)
    ap.add_argument("--min-loudness", type=float, default=0.3, help="ignore notes quieter than this (0 to 1)")
    ap.add_argument("--strict-octave", action="store_true", help="count a right note in the wrong octave as wrong")
    ap.add_argument("--rhythm-tolerance-ms", type=int, default=150, help="how far from the line of best fit still counts as on time")
    ap.add_argument("--score", default="notes,rhythm,tempo", help="which metrics make the final score: any of notes,rhythm,tempo")
    ap.add_argument("--rows", type=int, default=40, help="how many lines of the breakdown to print")
    args = ap.parse_args()
    chosen = {x.strip() for x in args.score.split(",")}
    settings = Settings(include_notes="notes" in chosen, include_rhythm="rhythm" in chosen, include_tempo="tempo" in chosen,
                        rhythm_tolerance_ms=args.rhythm_tolerance_ms, min_loudness=args.min_loudness,
                        octave_ok=not args.strict_octave)

    tmp = Path(tempfile.mkdtemp())
    ref = transcribe(args.reference, tmp / "reference.mid")
    stu = transcribe(args.student, tmp / "student.mid")
    c = compare(ref.notes, stu.notes, settings.min_loudness, settings.octave_ok)

    print(f"NOTES {100 * c.score:.0f}%   ({c.counts['correct'] + (c.counts['octave'] if c.octave_counts_as_correct else 0)}"
          f" of {c.reference_notes} reference notes)")
    print("  " + "   ".join(f"{k} {v}" for k, v in c.counts.items()))
    print(f"  student played {c.student_notes} notes and reached reference note {c.reached_note} of {c.reference_notes}")
    if c.shift:
        print(f"  NOTE: the student's recording is {c.shift:+d} semitone(s) from the reference; compared after shifting it")
    t = measure_timing(c, settings.rhythm_tolerance)
    print(f"TEMPO  {describe_tempo(t.tempo_percent)}")
    if t.rhythm_score is None:
        print(f"RHYTHM not enough matched notes ({t.matched})")
    else:
        print(f"RHYTHM {100 * t.rhythm_score:.0f}%   ({t.within_tolerance} of {t.matched} matched notes within "
              f"{1000 * t.tolerance:.0f} ms; typical error {t.typical_error_ms:.0f} ms; line fitted on {t.used_for_line})")
    score, parts, fell_back = final_score(c, t, settings)
    counted = ", ".join(f"{p.label.lower()} {100 * p.score:.0f}%" for p in parts if p.counted)
    print(f"FINAL  {100 * score:.0f}%   ({'note score, nothing selected' if fell_back else 'average of ' + counted})")
    print()
    print(f"  {'ref s':>6}  {'student s':>9}  {'timing':>12}  result")
    for k, r in enumerate(c.rows[: args.rows]):
        parts = []
        for n in r.notes:
            if n.label == "correct": parts.append(f"{n.name} ok")
            elif n.label == "octave": parts.append(f"{n.name} 8va({n.played})")
            elif n.label == "wrong": parts.append(f"{n.name} wrong({n.played})")
            else: parts.append(f"{n.name} missed")
        parts += [f"+{x} extra" for x in r.extras]
        rt = f"{r.ref_time:6.2f}" if r.ref_time is not None else "     -"
        st = f"{r.stu_time:9.2f}" if r.stu_time is not None else "        -"
        tm = f"{abs(r.offset_ms):5.0f} ms {'late' if r.offset_ms > 0 else 'early':<5}" if r.offset_ms is not None else " " * 12
        print(f"  {rt}  {st}  {tm}  {', '.join(parts)}")
    if len(c.rows) > args.rows:
        print(f"  ... {len(c.rows) - args.rows} more lines (use --rows to see more)")


if __name__ == "__main__":
    main()
