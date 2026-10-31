"""Evidence-chain tests: appends verify; a tampered line is caught."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scoring.chain import Store


class TestChain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "chain.jsonl"
        self.store = Store(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_append_and_verify(self):
        self.store.append("task_card", {"sealed": {"seal": "abc"}})
        self.store.append("run", {"run": {"run_id": "r1"}})
        rec = self.store.append("verdicts", {"grade": {"flag_count": 0}})
        self.assertEqual(rec["seq"], 3)
        verdict = self.store.verify_chain()
        self.assertTrue(verdict["ok"])
        self.assertEqual(verdict["records"], 3)
        self.assertIsNone(verdict["first_bad_seq"])

    def test_empty_chain_verifies(self):
        verdict = self.store.verify_chain()
        self.assertTrue(verdict["ok"])
        self.assertEqual(verdict["records"], 0)

    def test_tampered_payload_is_detected(self):
        self.store.append("run", {"run": {"run_id": "r1"}})
        self.store.append("run", {"run": {"run_id": "r2"}})
        lines = self.path.read_text(encoding="utf-8").splitlines()
        record = json.loads(lines[0])
        record["payload"]["run"]["run_id"] = "forged"
        lines[0] = json.dumps(record, sort_keys=True)
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        verdict = self.store.verify_chain()
        self.assertFalse(verdict["ok"])
        self.assertEqual(verdict["first_bad_seq"], 1)

    def test_unknown_record_type_refused(self):
        with self.assertRaises(ValueError):
            self.store.append("edit_history", {})


if __name__ == "__main__":
    unittest.main()
