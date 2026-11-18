"""Run with:  .venv/bin/python -m unittest"""

import unittest

from comparison import compare, group_events
from transcription import Note


def melody(pitches, loudness=0.8, step=0.5):
    return [Note(i * step, i * step + 0.4, p, loudness) for i, p in enumerate(pitches)]


SCALE = [60, 62, 64, 65, 67, 69, 71, 72]  # C4 to C5
TWINKLE = [60, 60, 67, 67, 69, 69, 67, 65, 65, 64, 64, 62, 62, 60]


class CompareTest(unittest.TestCase):
    def test_identical_takes_score_100(self):
        c = compare(melody(TWINKLE), melody(TWINKLE))
        self.assertEqual(c.score, 1.0)
        self.assertEqual(c.counts, {"correct": 14, "octave": 0, "wrong": 0, "missed": 0, "extra": 0})
        self.assertEqual(c.reached_note, 14)

    def test_missed_note(self):
        student = TWINKLE[:4] + TWINKLE[5:]  # skipped the fifth note
        c = compare(melody(TWINKLE), melody(student))
        self.assertEqual(c.counts["missed"], 1)
        self.assertEqual(c.counts["correct"], 13)
        self.assertAlmostEqual(c.score, 13 / 14)

    def test_wrong_note(self):
        student = list(TWINKLE); student[7] = 66  # F# instead of F
        c = compare(melody(TWINKLE), melody(student))
        self.assertEqual(c.counts["wrong"], 1)
        self.assertAlmostEqual(c.score, 13 / 14)
        wrong = [n for r in c.rows for n in r.notes if n.label == "wrong"][0]
        self.assertEqual((wrong.name, wrong.played), ("F4", "F#4"))

    def test_extra_note_does_not_lower_score(self):
        student = TWINKLE[:3] + [61] + TWINKLE[3:]
        c = compare(melody(TWINKLE), melody(student))
        self.assertEqual(c.counts["extra"], 1)
        self.assertEqual(c.counts["correct"], 14)
        self.assertEqual(c.score, 1.0)

    def test_quiet_notes_are_ignored(self):
        student = melody(TWINKLE) + [Note(1.25, 1.3, 96, 0.2)]  # a quiet ghost
        c = compare(melody(TWINKLE), student)
        self.assertEqual(c.counts["extra"], 0)
        self.assertEqual(c.student_notes, 14)

    def test_octave_counts_as_correct_by_default_but_can_be_strict(self):
        student = list(TWINKLE); student[2] = 79  # G5 instead of G4
        lenient = compare(melody(TWINKLE), melody(student))
        self.assertEqual(lenient.counts["octave"], 1)
        self.assertEqual(lenient.score, 1.0)
        strict = compare(melody(TWINKLE), melody(student), octave_counts_as_correct=False)
        self.assertAlmostEqual(strict.score, 13 / 14)

    def test_chord_note_order_does_not_matter(self):
        ref = [Note(0.00, 0.5, 60, 0.8), Note(0.01, 0.5, 64, 0.8), Note(0.02, 0.5, 67, 0.8)]
        stu = [Note(0.00, 0.5, 67, 0.8), Note(0.01, 0.5, 60, 0.8), Note(0.03, 0.5, 64, 0.8)]
        c = compare(ref, stu)
        self.assertEqual(c.score, 1.0)
        self.assertEqual(len(c.rows), 1)

    def test_missing_note_inside_a_chord(self):
        ref = [Note(0.00, 0.5, 60, 0.8), Note(0.01, 0.5, 64, 0.8), Note(0.02, 0.5, 67, 0.8)]
        stu = [Note(0.00, 0.5, 60, 0.8), Note(0.01, 0.5, 64, 0.8)]
        c = compare(ref, stu)
        self.assertEqual(c.counts["missed"], 1)
        self.assertAlmostEqual(c.score, 2 / 3)

    def test_whole_take_transposed_is_detected_and_corrected(self):
        student = [p + 1 for p in TWINKLE]
        c = compare(melody(TWINKLE), melody(student))
        self.assertEqual(c.shift, 1)
        self.assertEqual(c.score, 1.0)

    def test_a_few_wrong_notes_do_not_look_like_a_transposition(self):
        student = list(TWINKLE); student[0] = 61; student[5] = 70
        c = compare(melody(TWINKLE), melody(student))
        self.assertEqual(c.shift, 0)
        self.assertEqual(c.counts["wrong"], 2)

    def test_stopping_halfway(self):
        c = compare(melody(TWINKLE), melody(TWINKLE[:7]))
        self.assertEqual(c.reached_note, 7)
        self.assertEqual(c.counts["missed"], 7)
        self.assertAlmostEqual(c.score, 0.5)

    def test_empty_student(self):
        c = compare(melody(SCALE), [])
        self.assertEqual(c.score, 0.0)
        self.assertEqual(c.counts["missed"], 8)
        self.assertEqual(c.reached_note, 0)

    def test_grouping_window(self):
        notes = [Note(0.00, 0.5, 60, 0.8), Note(0.04, 0.5, 64, 0.8), Note(0.09, 0.5, 67, 0.8)]
        events = group_events(notes, 0.0)
        self.assertEqual([e.pitches for e in events], [(60, 64), (67,)])


if __name__ == "__main__":
    unittest.main()
