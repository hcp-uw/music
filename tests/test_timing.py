"""Run with:  .venv/bin/python -m unittest"""

import unittest

from comparison import compare
from timing import describe_tempo, measure_timing
from transcription import Note

TWINKLE = [60, 60, 67, 67, 69, 69, 67, 65, 65, 64, 64, 62, 62, 60]


def take(pitches, times, loudness=0.8):
    return [Note(t, t + 0.3, p, loudness) for p, t in zip(pitches, times)]


REF_TIMES = [0.5 * i for i in range(len(TWINKLE))]


class TimingTest(unittest.TestCase):
    def test_identical_take_is_perfect(self):
        c = compare(take(TWINKLE, REF_TIMES), take(TWINKLE, REF_TIMES))
        t = measure_timing(c)
        self.assertAlmostEqual(t.tempo_percent, 0.0, places=6)
        self.assertEqual(t.rhythm_score, 1.0)
        self.assertAlmostEqual(t.typical_error_ms, 0.0, places=6)
        self.assertEqual(describe_tempo(t.tempo_percent), "same tempo as the reference")

    def test_steadily_slower_is_a_tempo_not_a_rhythm_problem(self):
        slow = [1.2 * x + 0.8 for x in REF_TIMES]   # 20% slower, started 0.8 s later
        t = measure_timing(compare(take(TWINKLE, REF_TIMES), take(TWINKLE, slow)))
        self.assertAlmostEqual(t.tempo_percent, 20.0, places=6)
        self.assertEqual(t.rhythm_score, 1.0)
        self.assertEqual(describe_tempo(t.tempo_percent), "20% slower than the reference")

    def test_faster_is_described_as_faster(self):
        fast = [0.9 * x for x in REF_TIMES]
        t = measure_timing(compare(take(TWINKLE, REF_TIMES), take(TWINKLE, fast)))
        self.assertEqual(describe_tempo(t.tempo_percent), "10% faster than the reference")

    def test_one_late_note_is_flagged_and_does_not_tilt_the_line(self):
        times = list(REF_TIMES); times[6] += 0.3   # one note 300 ms late
        c = compare(take(TWINKLE, REF_TIMES), take(TWINKLE, times))
        t = measure_timing(c)
        self.assertAlmostEqual(t.tempo_percent, 0.0, places=6)   # stray point excluded from the fit
        self.assertEqual(t.within_tolerance, 13)
        self.assertAlmostEqual(t.rhythm_score, 13 / 14)
        self.assertEqual(t.used_for_line, 13)
        offsets = [r.offset_ms for r in c.rows]
        self.assertAlmostEqual(offsets[6], 300.0, places=3)
        for i, o in enumerate(offsets):
            if i != 6:
                self.assertAlmostEqual(o, 0.0, places=3)

    def test_early_note_has_negative_offset(self):
        times = list(REF_TIMES); times[3] -= 0.2
        c = compare(take(TWINKLE, REF_TIMES), take(TWINKLE, times))
        measure_timing(c)
        self.assertAlmostEqual(c.rows[3].offset_ms, -200.0, places=3)

    def test_uneven_rhythm_lowers_the_score(self):
        wobble = [x + (0.2 if i % 2 else -0.2) for i, x in enumerate(REF_TIMES)]  # every note 200 ms off
        t = measure_timing(compare(take(TWINKLE, REF_TIMES), take(TWINKLE, wobble)))
        self.assertEqual(t.rhythm_score, 0.0)
        self.assertAlmostEqual(t.typical_error_ms, 200.0, delta=40)  # the alternating pattern tilts the line a little

    def test_only_matched_notes_count(self):
        student = list(TWINKLE); student[4] = 61   # a wrong note has no timing
        c = compare(take(TWINKLE, REF_TIMES), take(student, REF_TIMES))
        t = measure_timing(c)
        self.assertEqual(t.matched, 13)
        self.assertIsNone(c.rows[4].offset_ms)

    def test_too_few_notes(self):
        c = compare(take(TWINKLE, REF_TIMES), take(TWINKLE[:3], REF_TIMES[:3]))
        t = measure_timing(c)
        self.assertIsNone(t.tempo_percent)
        self.assertIsNone(t.rhythm_score)
        self.assertEqual(describe_tempo(t.tempo_percent), "not enough matched notes to tell")


if __name__ == "__main__":
    unittest.main()
