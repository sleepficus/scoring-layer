"""Session 1.1 regression tests — one per Harbor audit finding.

Each test pins the FIXED behavior for a defect the independent audit
demonstrated against Session 1 (verdict FAIL, 2026-10-27). Every one
of these fails on the pre-fix code for the reason in its docstring.
"""

import contextlib
import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scoring import cli
from scoring.capture import load_fixture
from scoring.chain import GENESIS_PREV_HASH, Store, canonical
from scoring.graders import grade_run
from scoring.precision import compute_precision, decisions_from_chain
from scoring.scorecard import render_precision
from scoring.sealing import seal_task_card, verify_seal

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "synthetic_firecrawl.json"


def _rewrite_line(path: Path, index: int, mutate) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[index])
    mutate(record)
    lines[index] = json.dumps(record, sort_keys=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_demo_chain(path: Path) -> Store:
    """The Session 1 demo pipeline, appended to a fresh chain."""
    fixture = load_fixture(FIXTURE)
    store = Store(path)
    store.append("task_card", {"sealed": {"seal": "demo"}})
    for run in fixture["runs"]:
        store.append("run", {"run": run})
        store.append("verdicts",
                     {"grade": grade_run(run, fixture["task_card"])})
    for decision in fixture["human_decisions"]:
        store.append("queue_decision", decision)
    return store


class TestF1HashCoverage(unittest.TestCase):
    """F1 (High): the v1 hash covered only prev_hash + payload, so a
    record's type could be edited under a passing verify."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "chain.jsonl"
        self.store = Store(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_f1_type_tamper_breaks_verify(self):
        _build_demo_chain(self.path)
        # Seq 10 is a queue_decision carrying the kill decision;
        # retyping it removes the kill from the decision filter.
        _rewrite_line(self.path, 9,
                      lambda r: r.update(type="verdicts"))
        verdict = self.store.verify_chain()
        self.assertFalse(verdict["ok"])
        self.assertEqual(verdict["first_bad_seq"], 10)

    def test_f1_timestamp_tamper_breaks_verify(self):
        self.store.append("run", {"run": {"run_id": "r1"}})
        _rewrite_line(self.path, 0,
                      lambda r: r.update(ts="1999-01-01T00:00:00Z"))
        verdict = self.store.verify_chain()
        self.assertFalse(verdict["ok"])
        self.assertEqual(verdict["first_bad_seq"], 1)

    def test_f1_seq_tamper_breaks_verify(self):
        self.store.append("run", {"run": {"run_id": "r1"}})
        self.store.append("run", {"run": {"run_id": "r2"}})
        _rewrite_line(self.path, 1, lambda r: r.update(seq=7))
        verdict = self.store.verify_chain()
        self.assertFalse(verdict["ok"])

    def _write_v1_chain(self):
        def v1_hash(prev, payload):
            return hashlib.sha256(
                (prev + canonical(payload)).encode("utf-8")
            ).hexdigest()

        payload = {"run": {"run_id": "r1"}}
        record = {
            "seq": 1,
            "ts": "2026-10-27T16:00:00Z",
            "type": "run",
            "prev_hash": GENESIS_PREV_HASH,
            "hash": v1_hash(GENESIS_PREV_HASH, payload),
            "payload": payload,
        }
        self.path.write_text(json.dumps(record, sort_keys=True) + "\n",
                             encoding="utf-8")

    def test_f1_old_format_chain_rejected_not_misverified(self):
        self._write_v1_chain()
        verdict = self.store.verify_chain()
        self.assertFalse(verdict["ok"])
        self.assertEqual(verdict["first_bad_seq"], 1)
        self.assertIn("old chain format", verdict["error"])

    def test_f1_append_to_old_format_chain_refused(self):
        self._write_v1_chain()
        with self.assertRaises(ValueError) as ctx:
            self.store.append("run", {"run": {"run_id": "r2"}})
        self.assertIn("old chain format", str(ctx.exception))


class TestF2VerifyBeforeScore(unittest.TestCase):
    """F2 (Medium): precision-demo consumed a chain the verifier
    rejected and still printed a score."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "chain.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def _run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            rc = cli.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_f2_precision_refuses_bad_chain(self):
        _build_demo_chain(self.path)
        # Payload tamper: seq 10's kill becomes a confirm, hash stale.
        def flip(record):
            record["payload"]["decision"] = "confirm"

        _rewrite_line(self.path, 9, flip)
        rc, out, err = self._run_cli(
            ["precision-demo", "--chain", str(self.path)]
        )
        self.assertEqual(rc, 1)
        self.assertNotIn("OVERALL", out)
        self.assertIn("chain verification failed", err)

    def test_f2_precision_demo_good_chain_still_scores(self):
        _build_demo_chain(self.path)
        rc, out, _err = self._run_cli(
            ["precision-demo", "--chain", str(self.path)]
        )
        self.assertEqual(rc, 0)
        self.assertIn("OVERALL: precision 80.0%", out)

    def test_f2_verify_command_names_old_format(self):
        TestF1HashCoverage._write_v1_chain(self)
        rc, out, _err = self._run_cli(["verify", "--chain", str(self.path)])
        self.assertEqual(rc, 1)
        self.assertIn("old chain format", out)


class TestF3DecisionValidation(unittest.TestCase):
    """F3 (Medium): decisions counted without referring to a real,
    uniquely decided flag."""

    def setUp(self):
        fixture = load_fixture(FIXTURE)
        card = fixture["task_card"]
        self.flags = [
            flag for run in fixture["runs"]
            for flag in grade_run(run, card)["flags"]
        ]
        self.good = [dict(d) for d in fixture["human_decisions"]]

    def test_f3_fixture_decisions_still_valid(self):
        result = compute_precision(self.good, self.flags)
        self.assertEqual(result["overall"]["precision"], 0.8)

    def test_f3_orphan_decision_rejected(self):
        bad = self.good + [{
            "flag_id": "NEVER-EMITTED-FLAG",
            "grader": "completeness",
            "decision": "confirm",
        }]
        with self.assertRaises(ValueError) as ctx:
            compute_precision(bad, self.flags)
        self.assertIn("NEVER-EMITTED-FLAG", str(ctx.exception))

    def test_f3_duplicate_decision_rejected(self):
        bad = self.good + [dict(self.good[0])]
        with self.assertRaises(ValueError) as ctx:
            compute_precision(bad, self.flags)
        self.assertIn("duplicate", str(ctx.exception))

    def test_f3_missing_flag_id_rejected(self):
        bad = self.good + [{"grader": "completeness",
                            "decision": "confirm"}]
        with self.assertRaises(ValueError) as ctx:
            compute_precision(bad, self.flags)
        self.assertIn("flag_id", str(ctx.exception))

    def test_f3_wrong_grader_rejected(self):
        bad = [dict(d) for d in self.good]
        bad[0]["grader"] = "freshness"  # flag belongs to fetch-truth
        with self.assertRaises(ValueError) as ctx:
            compute_precision(bad, self.flags)
        self.assertIn("does not match", str(ctx.exception))


class TestF4SpendValidation(unittest.TestCase):
    """F4 (Medium): missing spend silently became zero; negative
    spend cancelled overspend."""

    def _load_mutated(self, mutate):
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        mutate(raw)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            return load_fixture(path)

    def test_f4_missing_spend_rejected(self):
        def mutate(raw):
            del raw["runs"][0]["fetches"][0]["response"]["creditsUsed"]

        with self.assertRaises(ValueError) as ctx:
            self._load_mutated(mutate)
        self.assertIn("creditsUsed", str(ctx.exception))

    def test_f4_missing_tokens_rejected(self):
        def mutate(raw):
            del raw["runs"][0]["fetches"][0]["tokensUsed"]

        with self.assertRaises(ValueError) as ctx:
            self._load_mutated(mutate)
        self.assertIn("tokensUsed", str(ctx.exception))

    def test_f4_negative_spend_cannot_cancel_overspend(self):
        def mutate(raw):
            raw["runs"][0]["fetches"][0]["response"]["creditsUsed"] = 100
            raw["runs"][0]["fetches"][1]["response"]["creditsUsed"] = -100

        with self.assertRaises(ValueError) as ctx:
            self._load_mutated(mutate)
        self.assertIn("creditsUsed", str(ctx.exception))

    def test_f4_non_numeric_spend_rejected(self):
        def mutate(raw):
            raw["runs"][0]["fetches"][0]["tokensUsed"] = "lots"

        with self.assertRaises(ValueError):
            self._load_mutated(mutate)

    def test_f4_valid_fixture_still_loads(self):
        fixture = self._load_mutated(lambda raw: None)
        self.assertEqual(len(fixture["runs"]), 2)


class TestF5EnvelopeCompleteness(unittest.TestCase):
    """F5 (Low): a seal envelope stripped of sealed_at /
    seal_algorithm still verified."""

    def setUp(self):
        card = load_fixture(FIXTURE)["task_card"]
        self.sealed = seal_task_card(card, "2026-10-27T15:55:00Z")

    def test_f5_complete_envelope_still_verifies(self):
        self.assertTrue(verify_seal(self.sealed))

    def test_f5_incomplete_envelope_fails(self):
        for drop in ("sealed_at", "seal_algorithm"):
            sealed = copy.deepcopy(self.sealed)
            del sealed[drop]
            self.assertFalse(verify_seal(sealed),
                             f"envelope without {drop} must not verify")

    def test_f5_invalid_timestamp_fails(self):
        sealed = copy.deepcopy(self.sealed)
        sealed["sealed_at"] = "not a timestamp"
        self.assertFalse(verify_seal(sealed))

    def test_f5_wrong_algorithm_fails(self):
        sealed = copy.deepcopy(self.sealed)
        sealed["seal_algorithm"] = "md5(canonical-json-v1)"
        self.assertFalse(verify_seal(sealed))


class TestF6DecisionReceipts(unittest.TestCase):
    """F6 (Low): precision output showed counts but no individual
    decision receipts."""

    def test_f6_precision_lists_decision_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "chain.jsonl")
            rec = store.append("queue_decision", {
                "flag_id": "run-x:fetch-truth:1",
                "grader": "fetch-truth",
                "decision": "confirm",
                "note": "checked by hand",
            })
            decisions = decisions_from_chain(store)
            out = render_precision(compute_precision(decisions))
        self.assertIn("Decision receipts:", out)
        self.assertIn("run-x:fetch-truth:1", out)
        self.assertIn("fetch-truth", out)
        self.assertIn("confirm", out)
        self.assertIn(f"chain seq {rec['seq']}", out)
        self.assertIn("checked by hand", out)


if __name__ == "__main__":
    unittest.main()
