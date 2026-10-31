"""Session 2 CLI tests: evidence reaches the user surface and chain."""

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from scoring import cli
from scoring.chain import Store
from scoring.capture import load_fixture
from scoring.graders import grade_session2_run


def task_pack():
    """A data-only pack unrelated to the enclosed two-run demo."""
    return {
        "synthetic": True,
        "task_card": {
            "id": "session2-interface-test", "freshness_bound_hours": 1,
            "cost_bound": {"max_credits": 10, "max_tokens": 1000},
            "questions": [{"id": "q1", "question": "What does it cost?",
                           "required_elements": ["$49 per month"]}],
        },
        "runs": [{
            "run_id": "session2-interface-run", "agent_label": "synthetic interface test",
            "started_at": "2026-10-27T16:00:00Z",
            "fetches": [{
                "url": "https://widgetforge.invalid/pricing", "relied_on": True,
                "question_ids": ["q1"], "tokensUsed": 100,
                "response": {"success": True, "creditsUsed": 1, "data": {
                    "markdown": "WidgetForge Pro costs $49 per month.",
                    "metadata": {"sourceURL": "https://widgetforge.invalid/pricing",
                                 "statusCode": 200, "cachedAt": "2026-10-27T15:55:00Z",
                                 "cacheState": "miss"},
                }},
            }],
            "final_answer": "WidgetForge Pro costs $49 per month. [source](https://widgetforge.invalid/pricing)",
        }],
        "human_decisions": [],
    }


class TestSession2Pipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.pack = self.root / "pack.json"
        self.chain = self.root / "chain.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = cli.main(argv)
        return result, out.getvalue(), err.getvalue()

    def save_pack(self, data=None):
        self.pack.write_text(json.dumps(data or task_pack()), encoding="utf-8")

    def test_default_cli_populates_original_fixture_claims_without_inventing_citations(self):
        rc, output, error = self.run_cli(["run", "--chain", str(self.chain)])
        self.assertEqual(rc, 0, error)
        self.assertIn("-- Claim support", output)
        self.assertIn("DETERMINISTIC", output)
        self.assertNotIn("Session 1 placeholder", output)
        store = Store(self.chain)
        self.assertTrue(store.verify_chain()["ok"])
        for record in store.iter_records(type="run"):
            run = record["payload"]["run"]
            self.assertTrue(run["claims"])
            self.assertTrue(all(not claim["citations"] for claim in run["claims"]))
        for record in store.iter_records(type="verdicts"):
            grade = record["payload"]["grade"]
            self.assertEqual(grade["session"], 2)
            self.assertTrue(grade["task_card_seal"])
            self.assertTrue(all(row["verdict"] == "UNSUPPORTED"
                                for row in grade["dimensions"]["Claim support"]["claims"]))

    def test_new_synthetic_pack_plugs_in_without_core_changes(self):
        self.save_pack()
        rc, output, error = self.run_cli(["run", "--pack", str(self.pack), "--chain", str(self.chain)])
        self.assertEqual(rc, 0, error)
        self.assertIn("SUPPORTED", output)
        self.assertIn("WidgetForge Pro costs $49 per month.", output)
        self.assertIn("https://widgetforge.invalid/pricing", output)
        grade = list(Store(self.chain).iter_records(type="verdicts"))[0]["payload"]["grade"]
        support = grade["dimensions"]["Claim support"]
        self.assertEqual(support["deterministic"]["SUPPORTED"], 1)
        self.assertEqual(support["judge"]["total"], 0)
        self.assertEqual(grade["claim_cost"]["deterministic"]["credits_per_supported_claim"], 1.0)

    def test_invalid_decisions_leave_new_chain_absent_and_print_no_score(self):
        pack = task_pack()
        pack["human_decisions"] = [{"flag_id": "orphan", "grader": "claim-support", "decision": "kill"}]
        self.save_pack(pack)
        rc, output, error = self.run_cli(["run", "--pack", str(self.pack), "--chain", str(self.chain)])
        self.assertEqual(rc, 1)
        self.assertIn("orphan", error)
        self.assertFalse(self.chain.exists())
        self.assertNotIn("SCORECARD", output)

    def test_duplicate_run_ids_rejected_before_chain_mutation(self):
        pack = task_pack()
        pack["runs"].append(copy.deepcopy(pack["runs"][0]))
        self.save_pack(pack)
        rc, output, error = self.run_cli(["run", "--pack", str(self.pack), "--chain", str(self.chain)])
        self.assertEqual(rc, 1)
        self.assertIn("duplicate run_id", error)
        self.assertFalse(self.chain.exists())
        self.assertNotIn("SCORECARD", output)

    def test_repeated_run_id_cannot_alias_existing_flags_or_decisions(self):
        self.save_pack()
        first = self.run_cli(["run", "--pack", str(self.pack), "--chain", str(self.chain)])
        self.assertEqual(first[0], 0, first[2])
        before = self.chain.read_bytes()
        rc, output, error = self.run_cli(["run", "--pack", str(self.pack), "--chain", str(self.chain)])
        self.assertEqual(rc, 1)
        self.assertIn("already exists", error)
        self.assertEqual(self.chain.read_bytes(), before)
        self.assertNotIn("SCORECARD", output)

    def test_card_id_reuse_with_changed_criteria_rejected(self):
        self.save_pack()
        first = self.run_cli(["run", "--pack", str(self.pack), "--chain", str(self.chain)])
        self.assertEqual(first[0], 0, first[2])
        before = self.chain.read_bytes()
        pack = task_pack()
        pack["runs"][0]["run_id"] = "new-run"
        pack["task_card"]["freshness_bound_hours"] = 2
        self.save_pack(pack)
        rc, output, error = self.run_cli(["run", "--pack", str(self.pack), "--chain", str(self.chain)])
        self.assertEqual(rc, 1)
        self.assertIn("different seal", error)
        self.assertEqual(self.chain.read_bytes(), before)

    def test_session1_remains_explicit_and_has_historical_counts(self):
        rc, output, error = self.run_cli(["run", "--session1", "--chain", str(self.chain)])
        self.assertEqual(rc, 0, error)
        self.assertIn("Session 1 compatibility", output)
        self.assertNotIn("-- Claim support", output)
        grades = [r["payload"]["grade"] for r in Store(self.chain).iter_records(type="verdicts")]
        self.assertEqual([g["flag_count"] for g in grades], [0, 5])

    def test_judge_supported_claim_stays_separate_on_scorecard_and_precision(self):
        pack = task_pack()
        raw_run = pack["runs"][0]
        raw_run["final_answer"] = "WidgetForge Pro costs $49 monthly [1]."
        raw_run["citations"] = {"1": "https://widgetforge.invalid/pricing"}
        text = raw_run["fetches"][0]["response"]["data"]["markdown"]
        raw_run["judge_decisions"] = [{
            "claim_id": raw_run["run_id"] + ":claim:1", "verdict": "SUPPORTED",
            "judge": {"seat": "SYNTHETIC judge fixture", "model": "SYNTHETIC model label",
                      "reviewed_at": "2026-10-27T16:01:00Z"},
            "reasoning": "SYNTHETIC review: monthly and per month express the same billing period.",
            "passages": [{"fetch_index": 0, "start": 0, "end": len(text), "text": text}],
        }]
        self.save_pack(pack)
        rc, output, error = self.run_cli(["run", "--pack", str(self.pack), "--chain", str(self.chain)])
        self.assertEqual(rc, 0, error)
        grade = list(Store(self.chain).iter_records(type="verdicts"))[0]["payload"]["grade"]
        self.assertEqual(grade["dimensions"]["Claim support"]["deterministic"]["SUPPORTED"], 0)
        self.assertEqual(grade["dimensions"]["Claim support"]["judge"]["SUPPORTED"], 1)
        self.assertIsNone(grade["claim_cost"]["deterministic"]["credits_per_supported_claim"])
        self.assertEqual(grade["claim_cost"]["judge"]["credits_per_supported_claim"], 1.0)
        self.assertIn("JUDGE supported-claim denominator: 1", output)
        self.assertIn("judge provenance:", output)
        # Even without --session2, the stored method prevents blended precision.
        rc, precision, error = self.run_cli(["precision-demo", "--chain", str(self.chain)])
        self.assertEqual(rc, 0, error)
        self.assertIn("DETERMINISTIC REVIEW PRECISION", precision)
        self.assertIn("JUDGE REVIEW PRECISION", precision)
        self.assertIn("SYNTHETIC fixture demonstration", precision)

    def test_invalid_judge_passage_fails_before_mutation(self):
        pack = task_pack()
        raw_run = pack["runs"][0]
        raw_run["final_answer"] = "WidgetForge Pro costs $49 monthly [1]."
        raw_run["citations"] = {"1": "https://widgetforge.invalid/pricing"}
        raw_run["judge_decisions"] = [{
            "claim_id": raw_run["run_id"] + ":claim:1", "verdict": "SUPPORTED",
            "judge": {"seat": "synthetic", "model": "synthetic", "reviewed_at": "2026-10-27T16:01:00Z"},
            "reasoning": "SYNTHETIC invalid passage probe",
            "passages": [{"fetch_index": 0, "start": 0, "end": 4, "text": "FAKE"}],
        }]
        self.save_pack(pack)
        rc, output, error = self.run_cli(["run", "--pack", str(self.pack), "--chain", str(self.chain)])
        self.assertEqual(rc, 1)
        self.assertIn("captured", error)
        self.assertFalse(self.chain.exists())
        self.assertNotIn("SCORECARD", output)

    def test_unknown_live_spend_does_not_turn_into_zero_or_cost_pass(self):
        self.save_pack()
        fixture = load_fixture(self.pack)
        run = fixture["runs"][0]
        run["synthetic"] = False
        fetch = run["fetches"][0]
        fetch["creditsUsed"] = None
        fetch["tokensUsed"] = None
        fetch["spend_status"] = {"creditsUsed": "UNKNOWN", "tokensUsed": "UNKNOWN"}
        grade = grade_session2_run(run, fixture["task_card"])
        cost = grade["dimensions"]["Cost truth"]
        self.assertIsNone(cost["cost"]["total_credits"])
        self.assertIsNone(cost["cost"]["total_tokens"])
        self.assertEqual(cost["flags"][0]["evidence"]["status"], "UNVERIFIABLE")
        self.assertIsNone(grade["claim_cost"]["deterministic"]["credits_per_supported_claim"])

    def test_mock_live_capture_reaches_cli_with_receipt_body_and_unknown_metering(self):
        from scoring.live import capture_live_task_pack
        raw = task_pack()
        source_run = raw["runs"][0]
        plan = {"task_card": raw["task_card"], "run_id": "mock-live-run",
                "agent_label": "SYNTHETIC transport test",
                "final_answer": source_run["final_answer"],
                "fetches": [{"url": "https://widgetforge.invalid/pricing", "relied_on": True,
                             "question_ids": ["q1"]}]}
        self.pack.write_text(json.dumps(plan), encoding="utf-8")
        capture_path = self.root / "capture.json"
        def fake_transport(request, timeout):
            response = {"success": True, "data": {"markdown": "WidgetForge Pro costs $49 per month.",
                        "metadata": {"sourceURL": "https://widgetforge.invalid/pricing", "statusCode": 200}}}
            return {"status_code": 200, "headers": {}, "body": json.dumps(response).encode("utf-8")}
        packet = capture_live_task_pack(self.pack, capture_path, transport=fake_transport)
        self.assertTrue(packet["synthetic"])
        rc, output, error = self.run_cli(["run", "--pack", str(capture_path), "--chain", str(self.chain)])
        self.assertEqual(rc, 0, error)
        self.assertIn("Credits spent: UNKNOWN", output)
        self.assertIn("tokens spent: UNKNOWN", output)
        record = list(Store(self.chain).iter_records(type="run"))[0]["payload"]["run"]
        self.assertEqual(record["capture_evidence"]["receipts"], packet["capture_receipts"])
        self.assertEqual(record["capture_origin"], "firecrawl-keyless-v1")
        self.assertTrue(record["claims"])

    def test_malformed_pack_is_named_error_without_traceback_or_chain(self):
        self.pack.write_text("{this is not JSON}", encoding="utf-8")
        rc, output, error = self.run_cli(["run", "--pack", str(self.pack), "--chain", str(self.chain)])
        self.assertEqual(rc, 1)
        self.assertIn("ERROR", error)
        self.assertNotIn("Traceback", error)
        self.assertFalse(self.chain.exists())


if __name__ == "__main__":
    unittest.main()
