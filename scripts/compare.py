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
from transcription import transcribe  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reference", type=Path)
    ap.add_argument("student", type=Path)
    ap.add_argument("--min-loudness", type=float, default=0.3, help="ignore notes quieter than this (0 to 1)")
    ap.add_argument("--strict-octave", action="store_true", help="count a right note in the wrong octave as wrong")
    ap.add_argument("--rows", type=int, default=40, help="how many lines of the breakdown to print")
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp())
    ref = transcribe(args.reference, tmp / "reference.mid")
    stu = transcribe(args.student, tmp / "student.mid")
    c = compare(ref.notes, stu.notes, args.min_loudness, not args.strict_octave)

    print(f"SCORE {100 * c.score:.0f}%   ({c.counts['correct'] + (c.counts['octave'] if c.octave_counts_as_correct else 0)}"
          f" of {c.reference_notes} reference notes)")
    print("  " + "   ".join(f"{k} {v}" for k, v in c.counts.items()))
    print(f"  student played {c.student_notes} notes and reached reference note {c.reached_note} of {c.reference_notes}")
    if c.shift:
        print(f"  NOTE: the student's recording is {c.shift:+d} semitone(s) from the reference; compared after shifting it")
    print()
    print(f"  {'ref s':>6}  {'student s':>9}  result")
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
        print(f"  {rt}  {st}  {', '.join(parts)}")
    if len(c.rows) > args.rows:
        print(f"  ... {len(c.rows) - args.rows} more lines (use --rows to see more)")


if __name__ == "__main__":
    main()
