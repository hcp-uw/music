"""Tempo and rhythm, measured from the note pairing that comparison.py produces.

Every correctly matched event gives two moments: when the reference played it and
when the student did. Plot reference time against student time and a steady
performance is a straight line. The slope is the tempo (1.12 means the student
took 12 percent longer, so played 12 percent slower). How far each point sits
above or below the line is how late or early that note was.

The line is fitted so that a few stray points cannot tilt it: fit, drop points
further than three times the median distance from the line, fit again. The dropped
points still get a late/early amount and still count in the rhythm score.

Known limitation (see PLAN.md): one line assumes one steady tempo for the whole take.
"""

from dataclasses import dataclass

import numpy as np

from comparison import Comparison

MIN_POINTS = 4          # fewer matched notes than this and timing is not reported
DEFAULT_TOLERANCE = 0.15  # seconds; a note within this of the line counts as on time


@dataclass
class Timing:
    tolerance: float
    matched: int                   # matched events with a timing (correct or octave)
    tempo_percent: float | None    # +12 means 12% slower than the reference, -8 means 8% faster
    rhythm_score: float | None     # share of matched events within the tolerance
    within_tolerance: int
    typical_error_ms: float | None  # median distance from the line, in ms
    used_for_line: int             # how many points the line was fitted on


def fit_line(ref: np.ndarray, stu: np.ndarray, tolerance: float):
    """Straight line stu = slope * ref + offset, ignoring stray points. Returns (slope, offset, kept)."""
    keep = np.ones(len(ref), dtype=bool)
    for _ in range(3):
        slope, offset = np.polyfit(ref[keep], stu[keep], 1)
        distance = np.abs(stu - (slope * ref + offset))
        cutoff = max(3 * float(np.median(distance[keep])), tolerance)
        new_keep = distance <= cutoff
        if new_keep.sum() < MIN_POINTS or np.array_equal(new_keep, keep):
            break
        keep = new_keep
    return float(slope), float(offset), keep


def measure_timing(c: Comparison, tolerance: float = DEFAULT_TOLERANCE) -> Timing:
    """Fill in each row's offset_ms and return tempo and rhythm figures."""
    rows = [r for r in c.rows
            if r.ref_time is not None and r.stu_time is not None
            and any(n.label in ("correct", "octave") for n in r.notes)]
    if len(rows) < MIN_POINTS:
        return Timing(tolerance, len(rows), None, None, 0, None, 0)

    ref = np.array([r.ref_time for r in rows])
    stu = np.array([r.stu_time for r in rows])
    slope, offset, kept = fit_line(ref, stu, tolerance)
    off = stu - (slope * ref + offset)   # positive = late, negative = early (seconds)
    for r, o in zip(rows, off):
        r.offset_ms = float(1000 * o)

    within = int((np.abs(off) <= tolerance).sum())
    return Timing(
        tolerance=tolerance,
        matched=len(rows),
        tempo_percent=100 * (slope - 1),
        rhythm_score=within / len(rows),
        within_tolerance=within,
        typical_error_ms=float(1000 * np.median(np.abs(off))),
        used_for_line=int(kept.sum()),
    )


def describe_tempo(tempo_percent: float | None) -> str:
    if tempo_percent is None:
        return "not enough matched notes to tell"
    if abs(tempo_percent) < 2:
        return "same tempo as the reference"
    word = "slower" if tempo_percent > 0 else "faster"
    return f"{abs(tempo_percent):.0f}% {word} than the reference"
