"""Deterministic grader tests over the synthetic fixtures."""

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scoring.capture import load_fixture
from scoring.graders import (
    cost_detail,
    grade_cost,
    grade_fetch_truth,
    grade_freshness,
    grade_run,
)

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "synthetic_firecrawl.json"


class FixtureCase(unittest.TestCase):
    def setUp(self):
        fixture = load_fixture(FIXTURE)
        self.card = fixture["task_card"]
        self.clean, self.failures = fixture["runs"]


class TestCleanRun(FixtureCase):
    def test_clean_run_produces_zero_flags(self):
        result = grade_run(self.clean, self.card)
        self.assertEqual(result["flag_count"], 0)
        for dim in result["dimensions"].values():
            self.assertEqual(dim["flag_count"], 0)


class TestFetchTruth(FixtureCase):
    def test_403_delivered_as_document_is_caught(self):
        flags = grade_fetch_truth(self.failures)
        self.assertEqual(len(flags), 1)
        flag = flags[0]
        self.assertEqual(flag["subject"], "https://widgetforge.invalid/pricing")
        self.assertEqual(flag["evidence"]["statusCode"], 403)

    def test_block_page_under_200_is_caught_by_shape(self):
        run = copy.deepcopy(self.clean)
        run["fetches"][0]["content_markdown"] = (
            "Just a moment... Checking your browser before accessing."
        )
        run["fetches"][0]["statusCode"] = 200
        flags = grade_fetch_truth(run)
        self.assertEqual(len(flags), 1)
        self.assertTrue(
            any("block/challenge" in r for r in flags[0]["evidence"]["reasons"])
        )

    def test_unrelied_fetch_is_not_flagged(self):
        run = copy.deepcopy(self.failures)
        run["fetches"][0]["relied_on"] = False
        self.assertEqual(grade_fetch_truth(run), [])


class TestFreshness(FixtureCase):
    def test_seven_hour_cache_against_one_hour_bound_is_caught(self):
        flags = grade_freshness(self.failures, self.card)
        self.assertEqual(len(flags), 1)
        evidence = flags[0]["evidence"]
        self.assertEqual(evidence["age_hours"], 7.0)
        self.assertEqual(evidence["bound_hours"], 1)
        self.assertEqual(evidence["cachedAt"], "2026-10-27T09:00:00Z")

    def test_fresh_cache_passes(self):
        self.assertEqual(grade_freshness(self.clean, self.card), [])


class TestCompleteness(FixtureCase):
    def test_missing_elements_flagged_with_receipts(self):
        result = grade_run(self.failures, self.card)
        dim = result["dimensions"]["Completeness"]
        self.assertEqual(dim["required_elements"], 4)
        self.assertEqual(dim["present_elements"], 1)
        self.assertEqual(dim["missing_elements"], 3)
        missing = {
            f["evidence"]["missing_element"] for f in dim["flags"]
        }
        self.assertEqual(
            missing, {"WidgetForge Pro", "$49 per month", "1,200 requests"}
        )

    def test_planted_formatting_variant_flag_exists(self):
        # The fixture's q2 content carries '1200 requests' where the
        # sealed card requires '1,200 requests'. The naive substring
        # grader flags it; the fixture's human decision kills it.
        # This test pins the behavior so the planted beat cannot
        # silently disappear.
        result = grade_run(self.failures, self.card)
        subjects = {f["subject"] for f in result["dimensions"]["Completeness"]["flags"]}
        self.assertIn("q2: 1,200 requests", subjects)


class TestCostTruth(FixtureCase):
    def test_cost_per_verified_fact_arithmetic(self):
        cost = cost_detail(self.clean, self.card)
        self.assertEqual(cost["total_credits"], 2)
        self.assertEqual(cost["total_tokens"], 1400)
        self.assertEqual(cost["verified_facts"], 4)
        self.assertEqual(cost["credits_per_verified_fact"], 0.5)
        self.assertEqual(cost["tokens_per_verified_fact"], 350.0)

    def test_over_bound_spend_is_flagged(self):
        card = copy.deepcopy(self.card)
        card["cost_bound"] = {"max_credits": 1, "max_tokens": 20000}
        flags = grade_cost(self.clean, card)
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]["evidence"]["total_credits"], 2)


if __name__ == "__main__":
    unittest.main()
