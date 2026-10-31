"""User-facing honesty beat on the separate synthetic data pack."""
import tempfile
import unittest
from pathlib import Path

from scoring.capture import load_task_pack
from scoring.graders import grade_session2_run
from scoring.precision import compute_precision

ROOT = Path(__file__).resolve().parent.parent


class TestDemoPack(unittest.TestCase):
    def test_planted_semantic_miss_lowers_precision_without_changing_verdict(self):
        pack = load_task_pack(ROOT / 'fixtures/session2_claim_support.json')
        result = grade_session2_run(pack['runs'][0], pack['task_card'])
        dimension = result['dimensions']['Claim support']
        self.assertEqual(dimension['deterministic'], {
            'SUPPORTED': 2, 'UNSUPPORTED': 2, 'CONTRADICTED': 1, 'total': 5})
        flags = result['flags']
        before = compute_precision(pack['human_decisions'][:2], flags)
        after = compute_precision(pack['human_decisions'], flags)
        self.assertEqual(before['per_grader']['claim-support']['precision'], 1.0)
        self.assertEqual(after['per_grader']['claim-support']['precision'], .6667)
        self.assertEqual(dimension['claims'][4]['verdict'], 'UNSUPPORTED')
        self.assertTrue(dimension['claims'][4]['needs_judge'])

    def test_judge_import_demo_preserves_deterministic_counts(self):
        pack = load_task_pack(ROOT / 'fixtures/session2_judge_demo.json')
        run = pack['runs'][0]
        result = grade_session2_run(run, pack['task_card'], run['judge_decisions'])
        dimension = result['dimensions']['Claim support']
        self.assertEqual(dimension['deterministic']['SUPPORTED'], 2)
        self.assertEqual(dimension['judge']['SUPPORTED'], 1)
        self.assertIn('SYNTHETIC', dimension['judge_claims'][0]['judge']['seat'])


if __name__ == '__main__':
    unittest.main()
