"""Run with:  .venv/bin/python -m unittest"""

import unittest

from comparison import compare
from scoring import Settings, final_score, tempo_score
from timing import Timing, measure_timing
from transcription import Note

TWINKLE = [60, 60, 67, 67, 69, 69, 67, 65, 65, 64, 64, 62, 62, 60]


def take(pitches, times):
    return [Note(t, t + 0.3, p, 0.8) for p, t in zip(pitches, times)]


REF_TIMES = [0.5 * i for i in range(len(TWINKLE))]


class TempoScoreTest(unittest.TestCase):
    def test_shape(self):
        self.assertEqual(tempo_score(0), 1.0)
        self.assertEqual(tempo_score(5), 1.0)
        self.assertEqual(tempo_score(-5), 1.0)
        self.assertAlmostEqual(tempo_score(27.5), 0.5)
        self.assertEqual(tempo_score(50), 0.0)
        self.assertEqual(tempo_score(-80), 0.0)
        self.assertIsNone(tempo_score(None))


class SettingsTest(unittest.TestCase):
    def test_defaults(self):
        s = Settings()
        self.assertTrue(s.include_notes and s.include_rhythm and s.include_tempo)
        self.assertEqual(s.rhythm_tolerance_ms, 150)

    def test_bad_values_are_clamped_or_ignored(self):
        s = Settings.from_dict({"rhythm_tolerance_ms": "5", "min_loudness": "7", "include_tempo": 1})
        self.assertEqual(s.rhythm_tolerance_ms, 50)
        self.assertEqual(s.min_loudness, 1.0)
        self.assertTrue(s.include_tempo)
        s = Settings.from_dict({"rhythm_tolerance_ms": "lots"})
        self.assertEqual(s.rhythm_tolerance_ms, 150)

    def test_round_trip(self):
        s = Settings(include_tempo=True, rhythm_tolerance_ms=300)
        self.assertEqual(Settings.from_dict(s.to_dict()), s)


class FinalScoreTest(unittest.TestCase):
    def setUp(self):
        student = list(TWINKLE); student[3] = 61; student[8] = 61   # two wrong notes -> notes 12/14
        times = list(REF_TIMES); times[5] += 0.3                      # one late note -> rhythm 11/12
        self.c = compare(take(TWINKLE, REF_TIMES), take(student, times))
        self.t = measure_timing(self.c, 0.15)

    def test_default_is_average_of_all_three(self):
        score, parts, fell_back = final_score(self.c, self.t, Settings())
        self.assertAlmostEqual(score, (12 / 14 + 11 / 12 + 1.0) / 3)   # same tempo -> tempo score 1
        self.assertEqual([p.counted for p in parts], [True, True, True])
        self.assertFalse(fell_back)

    def test_tempo_can_be_switched_off(self):
        score, parts, _ = final_score(self.c, self.t, Settings(include_tempo=False))
        self.assertAlmostEqual(score, (12 / 14 + 11 / 12) / 2)
        self.assertEqual([p.counted for p in parts], [True, True, False])

    def test_notes_only(self):
        score, _, _ = final_score(self.c, self.t, Settings(include_rhythm=False, include_tempo=False))
        self.assertAlmostEqual(score, 12 / 14)

    def test_unmeasurable_metric_is_left_out(self):
        no_timing = Timing(0.15, 2, None, None, 0, None, 0)
        score, parts, fell_back = final_score(self.c, no_timing, Settings())
        self.assertAlmostEqual(score, 12 / 14)
        self.assertEqual([p.counted for p in parts], [True, False, False])
        self.assertFalse(fell_back)

    def test_nothing_selected_falls_back_to_notes(self):
        score, parts, fell_back = final_score(self.c, self.t, Settings(include_notes=False, include_rhythm=False, include_tempo=False))
        self.assertAlmostEqual(score, 12 / 14)
        self.assertTrue(fell_back)
        self.assertTrue(parts[0].counted)

    def test_tolerance_setting_changes_rhythm(self):
        loose = measure_timing(self.c, Settings(rhythm_tolerance_ms=400).rhythm_tolerance)
        self.assertEqual(loose.rhythm_score, 1.0)


if __name__ == "__main__":
    unittest.main()
