"""Grader-precision math tests on known confirm/kill sets."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scoring.capture import load_fixture
from scoring.graders import grade_run
from scoring.precision import compute_precision

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "synthetic_firecrawl.json"


class TestPrecision(unittest.TestCase):
    def test_known_confirm_kill_set(self):
        decisions = [
            {"flag_id": "r:g1:1", "grader": "g1", "decision": "confirm"},
            {"flag_id": "r:g1:2", "grader": "g1", "decision": "confirm"},
            {"flag_id": "r:g1:3", "grader": "g1", "decision": "kill"},
            {"flag_id": "r:g2:1", "grader": "g2", "decision": "kill"},
        ]
        result = compute_precision(decisions)
        self.assertEqual(result["per_grader"]["g1"]["precision"], round(2 / 3, 4))
        self.assertEqual(result["per_grader"]["g2"]["precision"], 0.0)
        self.assertEqual(result["overall"]["precision"], 0.5)
        self.assertEqual(result["overall"]["confirmed"], 2)
        self.assertEqual(result["overall"]["killed"], 2)

    def test_no_decisions_is_unverified_not_perfect(self):
        result = compute_precision([])
        self.assertIsNone(result["overall"]["precision"])

    def test_pending_flags_counted_from_flag_list(self):
        flags = [
            {"flag_id": "r:g1:1", "grader": "g1"},
            {"flag_id": "r:g1:2", "grader": "g1"},
        ]
        decisions = [
            {"flag_id": "r:g1:1", "grader": "g1", "decision": "confirm"},
        ]
        result = compute_precision(decisions, flags)
        self.assertEqual(result["per_grader"]["g1"]["pending"], 1)
        self.assertEqual(result["overall"]["pending"], 1)

    def test_unknown_decision_refused(self):
        with self.assertRaises(ValueError):
            compute_precision(
                [{"flag_id": "x", "grader": "g", "decision": "shrug"}]
            )

    def test_fixture_demonstration_numbers(self):
        fixture = load_fixture(FIXTURE)
        card = fixture["task_card"]
        all_flags = [
            flag for run in fixture["runs"]
            for flag in grade_run(run, card)["flags"]
        ]
        result = compute_precision(fixture["human_decisions"], all_flags)
        # Fixture decisions: fetch-truth 1 confirm; freshness 1 confirm;
        # completeness 2 confirm + 1 kill (the planted grader error).
        self.assertEqual(result["per_grader"]["fetch-truth"]["precision"], 1.0)
        self.assertEqual(result["per_grader"]["freshness"]["precision"], 1.0)
        self.assertEqual(
            result["per_grader"]["completeness"]["precision"], round(2 / 3, 4)
        )
        self.assertEqual(result["overall"]["precision"], 0.8)
        self.assertEqual(result["overall"]["pending"], 0)


if __name__ == "__main__":
    unittest.main()
