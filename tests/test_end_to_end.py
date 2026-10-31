"""End-to-end: fixture -> seal -> grade -> chain -> verify."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scoring.capture import load_fixture
from scoring.chain import Store
from scoring.graders import grade_run
from scoring.precision import compute_precision, decisions_from_chain
from scoring.sealing import seal_task_card, verify_seal

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "synthetic_firecrawl.json"


class TestEndToEnd(unittest.TestCase):
    def test_full_pipeline_over_fixtures(self):
        fixture = load_fixture(FIXTURE)
        card = fixture["task_card"]
        sealed = seal_task_card(card, "2026-10-27T15:55:00Z")
        self.assertTrue(verify_seal(sealed))
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "chain.jsonl")
            store.append("task_card", {"sealed": sealed})
            counts = {}
            for run in fixture["runs"]:
                result = grade_run(run, card)
                counts[run["run_id"]] = result["flag_count"]
                store.append("run", {"run": run})
                store.append("verdicts", {"grade": result})
            self.assertEqual(counts["run-synthetic-clean"], 0)
            # fetch-truth 1 + freshness 1 + completeness 3 + cost 0
            self.assertEqual(counts["run-synthetic-failures"], 5)
            for decision in fixture["human_decisions"]:
                store.append("queue_decision", decision)
            verdict = store.verify_chain()
            self.assertTrue(verdict["ok"])
            # 1 task_card + 2 runs x (run + verdicts) + 5 decisions
            self.assertEqual(verdict["records"], 10)
            chained_decisions = decisions_from_chain(store)
            self.assertEqual(len(chained_decisions), 5)
            precision = compute_precision(chained_decisions)
            self.assertEqual(precision["overall"]["precision"], 0.8)

    def test_fixture_refuses_unlabeled_data(self):
        import json
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["synthetic"] = False
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_fixture(path)


if __name__ == "__main__":
    unittest.main()
