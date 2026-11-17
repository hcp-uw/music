"""Compare a student's notes to a reference performance, note by note.

Both sides are lists of transcription.Note. Timing is ignored, except that notes
starting within 50 ms of each other are grouped into one chord. The two sequences
are lined up with the classic edit-distance table, and every reference note gets
one label:

    correct   the same pitch was played in its place
    octave    the same note name was played, but in another octave
    wrong     a different note was played in its place
    missed    nothing was played in its place

Student notes with no reference counterpart are "extra". The score is the share of
reference notes that were correct. By default an octave match counts as correct.
Extra notes are reported but never lower the score, because the transcriber's
most common mistake is inventing a quiet extra note.
"""

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pretty_midi

from transcription import Note

CHORD_WINDOW = 0.05          # notes starting this close together are one chord
COST = {"correct": 0.0, "octave": 0.5, "wrong": 1.0, "missed": 1.0}
EXTRA_COST = 0.5             # cost of an unmatched student note when lining up
MIN_NOTES_FOR_SHIFT = 8      # do not guess a transposition from fewer notes


@dataclass
class Event:
    """One moment in a performance: a single note or a chord."""
    start: float
    pitches: tuple[int, ...]


@dataclass
class RowNote:
    name: str            # reference note name, e.g. "C4"
    label: str           # correct, octave, wrong, missed
    played: str | None   # what the student played instead, for octave and wrong


@dataclass
class Row:
    """One line of the note-by-note breakdown."""
    ref_time: float | None
    stu_time: float | None
    notes: list[RowNote]   # reference notes in this event with their labels
    extras: list[str]      # student notes in this event with no reference counterpart


@dataclass
class Comparison:
    score: float                 # 0 to 1
    counts: dict[str, int]       # correct, octave, wrong, missed, extra
    reference_notes: int         # reference notes after the loudness filter
    student_notes: int
    reached_note: int            # the last reference note the student got to (1-based), 0 if none
    shift: int                   # semitones the student was above the reference; 0 if none detected
    octave_counts_as_correct: bool
    min_loudness: float
    rows: list[Row]


def group_events(notes: list[Note], min_loudness: float) -> list[Event]:
    """Drop quiet notes and group notes that start together into chords."""
    events: list[Event] = []
    for n in sorted(notes, key=lambda n: n.start):
        if n.loudness < min_loudness:
            continue
        if events and n.start - events[-1].start <= CHORD_WINDOW:
            events[-1].pitches = tuple(sorted(events[-1].pitches + (n.pitch,)))
        else:
            events.append(Event(n.start, (n.pitch,)))
    return events


def detect_shift(ref: list[Event], stu: list[Event]) -> int:
    """Semitones the student is above the reference, if the whole take is transposed.

    Compares how often each of the 12 note names is used. Only reports a shift when
    it is clearly better than no shift, so a few wrong notes never trigger it.
    """
    def hist(events):
        h = np.zeros(12)
        for e in events:
            for p in e.pitches:
                h[p % 12] += 1
        return h
    hr, hs = hist(ref), hist(stu)
    if hr.sum() < MIN_NOTES_FOR_SHIFT or hs.sum() < MIN_NOTES_FOR_SHIFT or hr.std() == 0 or hs.std() == 0:
        return 0
    corr = {k: float(np.corrcoef(np.roll(hs, -k), hr)[0, 1]) for k in range(-6, 6)}
    best = max(corr, key=corr.get)
    return best if corr[best] - corr[0] > 0.1 else 0


@lru_cache(maxsize=None)
def pair_chord(ref: tuple[int, ...], stu: tuple[int, ...]):
    """Pair the notes of one reference chord with one student chord.

    Exact matches first, then octave matches, then whatever is left is paired as
    wrong notes (closest pitch first). Returns (cost, labels, extra student pitches).
    """
    left = list(stu)
    labels: list[tuple[int, str, int | None]] = []
    pending = []
    for p in ref:
        if p in left:
            left.remove(p)
            labels.append((p, "correct", p))
        else:
            pending.append(p)
    still = []
    for p in pending:
        m = next((q for q in left if q % 12 == p % 12), None)
        if m is None:
            still.append(p)
        else:
            left.remove(m)
            labels.append((p, "octave", m))
    for p in still:
        if left:
            m = min(left, key=lambda q: abs(q - p))
            left.remove(m)
            labels.append((p, "wrong", m))
        else:
            labels.append((p, "missed", None))
    cost = sum(COST[label] for _, label, _ in labels) + EXTRA_COST * len(left)
    return cost, tuple(labels), tuple(left)


def align(ref: list[Event], stu: list[Event]) -> list[tuple[int | None, int | None]]:
    """Line up two event lists. Returns pairs of indexes; None means no counterpart.

    cost[i][j] is the cheapest way to line up the first i reference events with the
    first j student events. Each cell comes from one of three neighbours: pair the
    two events (diagonal), treat the reference event as missed (up), or treat the
    student event as extra (left). Walking back from the last cell gives the pairing.
    """
    n, m = len(ref), len(stu)
    cost = [[0.0] * (m + 1) for _ in range(n + 1)]
    move = [bytearray(m + 1) for _ in range(n + 1)]   # 0 diagonal, 1 up, 2 left
    for i in range(1, n + 1):
        cost[i][0] = cost[i - 1][0] + len(ref[i - 1].pitches) * COST["missed"]
        move[i][0] = 1
    for j in range(1, m + 1):
        cost[0][j] = cost[0][j - 1] + len(stu[j - 1].pitches) * EXTRA_COST
        move[0][j] = 2
    for i in range(1, n + 1):
        rp = ref[i - 1].pitches
        missed = len(rp) * COST["missed"]
        row, prev, mv = cost[i], cost[i - 1], move[i]
        for j in range(1, m + 1):
            sp = stu[j - 1].pitches
            diag = prev[j - 1] + pair_chord(rp, sp)[0]
            up = prev[j] + missed
            left = row[j - 1] + len(sp) * EXTRA_COST
            if diag <= up and diag <= left:
                row[j], mv[j] = diag, 0
            elif up <= left:
                row[j], mv[j] = up, 1
            else:
                row[j], mv[j] = left, 2
    steps = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and move[i][j] == 0:
            steps.append((i - 1, j - 1)); i -= 1; j -= 1
        elif i > 0 and (j == 0 or move[i][j] == 1):
            steps.append((i - 1, None)); i -= 1
        else:
            steps.append((None, j - 1)); j -= 1
    return steps[::-1]


def compare(reference: list[Note], student: list[Note], min_loudness: float = 0.3,
            octave_counts_as_correct: bool = True) -> Comparison:
    """Score a student's notes against a reference. Both are transcription.Note lists."""
    ref = group_events(reference, min_loudness)
    stu = group_events(student, min_loudness)
    shift = detect_shift(ref, stu)
    if shift:
        stu = [Event(e.start, tuple(p - shift for p in e.pitches)) for e in stu]

    name = pretty_midi.note_number_to_name
    counts = {"correct": 0, "octave": 0, "wrong": 0, "missed": 0, "extra": 0}
    rows: list[Row] = []
    reached = 0
    seen_ref_notes = 0
    for i, j in align(ref, stu):
        if i is not None and j is not None:
            _, labels, extras = pair_chord(ref[i].pitches, stu[j].pitches)
            notes = [RowNote(name(p), label, name(q) if q is not None and label != "correct" else None)
                     for p, label, q in labels]
            extra_names = [name(q) for q in extras]
            seen_ref_notes += len(ref[i].pitches)
            reached = seen_ref_notes
            rows.append(Row(ref[i].start, stu[j].start, notes, extra_names))
        elif i is not None:
            notes = [RowNote(name(p), "missed", None) for p in ref[i].pitches]
            extra_names = []
            seen_ref_notes += len(ref[i].pitches)
            rows.append(Row(ref[i].start, None, notes, []))
        else:
            notes = []
            extra_names = [name(q) for q in stu[j].pitches]
            rows.append(Row(None, stu[j].start, [], extra_names))
        for rn in notes:
            counts[rn.label] += 1
        counts["extra"] += len(extra_names)

    reference_notes = sum(len(e.pitches) for e in ref)
    student_notes = sum(len(e.pitches) for e in stu)
    good = counts["correct"] + (counts["octave"] if octave_counts_as_correct else 0)
    score = good / reference_notes if reference_notes else 0.0
    return Comparison(score, counts, reference_notes, student_notes, reached, shift,
                      octave_counts_as_correct, min_loudness, rows)
