"""User settings and the final score.

The final score is the plain average of whichever metrics the user has chosen to
count: notes (comparison.py), rhythm and tempo (timing.py). Tempo is a percentage
slower or faster, so it is turned into a 0 to 1 score first: full marks within
TEMPO_FREE percent of the reference, falling in a straight line to zero at
TEMPO_ZERO percent off. All three metrics count by default; the user can switch any
of them off in Advanced settings (the plan allows "turn off tempo checking").
"""

from dataclasses import asdict, dataclass

from comparison import Comparison
from timing import Timing

TEMPO_FREE = 5.0    # percent off the reference tempo that still gets full marks
TEMPO_ZERO = 50.0   # percent off at which the tempo score reaches zero


@dataclass
class Settings:
    include_notes: bool = True
    include_rhythm: bool = True
    include_tempo: bool = True
    rhythm_tolerance_ms: int = 150   # how far from the line of best fit a note may be and still count as on time
    min_loudness: float = 0.3        # notes quieter than this are ignored on both sides
    octave_ok: bool = True           # a right note in the wrong octave counts as correct

    @classmethod
    def from_dict(cls, d: dict) -> "Settings":
        """Build settings from stored or submitted values, falling back to defaults on anything odd."""
        s = cls()
        for key in ("include_notes", "include_rhythm", "include_tempo", "octave_ok"):
            if key in d:
                setattr(s, key, bool(d[key]))
        try:
            s.rhythm_tolerance_ms = int(min(2000, max(50, int(float(d.get("rhythm_tolerance_ms", s.rhythm_tolerance_ms))))))
        except (TypeError, ValueError):
            pass
        try:
            s.min_loudness = float(min(1.0, max(0.0, float(d.get("min_loudness", s.min_loudness)))))
        except (TypeError, ValueError):
            pass
        return s

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def rhythm_tolerance(self) -> float:
        return self.rhythm_tolerance_ms / 1000

    def summary(self) -> str:
        counted = [n for n, on in (("notes", self.include_notes), ("rhythm", self.include_rhythm), ("tempo", self.include_tempo)) if on]
        return (f"final score from {' + '.join(counted) if counted else 'notes (nothing selected)'} · "
                f"rhythm tolerance {self.rhythm_tolerance_ms} ms · notes quieter than {self.min_loudness:.2f} ignored · "
                f"wrong octave {'counts as correct' if self.octave_ok else 'counts as wrong'}")


def tempo_score(tempo_percent: float | None) -> float | None:
    """0 to 1: full marks within TEMPO_FREE percent of the reference, zero at TEMPO_ZERO."""
    if tempo_percent is None:
        return None
    off = abs(tempo_percent)
    if off <= TEMPO_FREE:
        return 1.0
    if off >= TEMPO_ZERO:
        return 0.0
    return 1.0 - (off - TEMPO_FREE) / (TEMPO_ZERO - TEMPO_FREE)


@dataclass
class Part:
    key: str
    label: str
    score: float | None   # None when it could not be measured
    included: bool        # the user asked for it to count
    counted: bool         # it actually went into the average (included and measurable)


def final_score(c: Comparison, t: Timing, s: Settings) -> tuple[float, list[Part], bool]:
    """Average of the chosen metrics. Returns (score, parts, fell_back_to_notes)."""
    parts = [
        Part("notes", "Notes", c.score, s.include_notes, False),
        Part("rhythm", "Rhythm", t.rhythm_score, s.include_rhythm, False),
        Part("tempo", "Tempo", tempo_score(t.tempo_percent), s.include_tempo, False),
    ]
    for p in parts:
        p.counted = p.included and p.score is not None
    used = [p.score for p in parts if p.counted]
    if used:
        return sum(used) / len(used), parts, False
    parts[0].counted = True   # nothing usable was chosen: fall back to the note score
    return c.score, parts, True
