"""Sealing tests: a sealed card verifies; any post-seal edit fails."""

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scoring.capture import load_fixture
from scoring.sealing import seal_task_card, verify_seal

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "synthetic_firecrawl.json"


class TestSealing(unittest.TestCase):
    def setUp(self):
        self.card = load_fixture(FIXTURE)["task_card"]
        self.sealed = seal_task_card(self.card, "2026-10-27T15:55:00Z")

    def test_fresh_seal_verifies(self):
        self.assertTrue(verify_seal(self.sealed))

    def test_tampered_question_text_detected(self):
        sealed = copy.deepcopy(self.sealed)
        sealed["card"]["questions"][0]["question"] = "What does it cost?"
        self.assertFalse(verify_seal(sealed))

    def test_tampered_freshness_bound_detected(self):
        sealed = copy.deepcopy(self.sealed)
        sealed["card"]["freshness_bound_hours"] = 24
        self.assertFalse(verify_seal(sealed))

    def test_tampered_required_element_detected(self):
        sealed = copy.deepcopy(self.sealed)
        sealed["card"]["questions"][0]["required_elements"] = ["WidgetForge Pro"]
        self.assertFalse(verify_seal(sealed))

    def test_tampered_seal_value_detected(self):
        sealed = copy.deepcopy(self.sealed)
        sealed["seal"] = "0" * 64
        self.assertFalse(verify_seal(sealed))


if __name__ == "__main__":
    unittest.main()
