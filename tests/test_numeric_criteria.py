"""Audit A5: non-finite or boolean criteria cannot suppress flags."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from scoring import cli
from scoring.capture import load_fixture
from scoring.sealing import validate_card, seal_task_card, verify_seal

FIXTURE = Path(__file__).resolve().parent.parent / 'fixtures/synthetic_firecrawl.json'
BAD = (float('nan'), float('inf'), float('-inf'), True, False)


class TestNumericCriteria(unittest.TestCase):
    def setUp(self):
        self.card = load_fixture(FIXTURE)['task_card']

    def test_card_freshness_requires_positive_finite_nonboolean(self):
        for value in BAD + (0, -1):
            with self.subTest(value=value):
                card = copy.deepcopy(self.card)
                card['freshness_bound_hours'] = value
                with self.assertRaises(ValueError):
                    validate_card(card)

    def test_question_override_requires_positive_finite_nonboolean(self):
        for value in BAD + (0, -1):
            with self.subTest(value=value):
                card = copy.deepcopy(self.card)
                card['questions'][0]['freshness_bound_hours'] = value
                with self.assertRaises(ValueError):
                    validate_card(card)

    def test_cost_bounds_reject_nonfinite_and_boolean(self):
        for field in ('max_credits', 'max_tokens'):
            for value in BAD + (-1,):
                with self.subTest(field=field, value=value):
                    card = copy.deepcopy(self.card)
                    card['cost_bound'][field] = value
                    with self.assertRaises(ValueError):
                        validate_card(card)

    def test_valid_fractional_freshness_and_zero_cost_still_seal(self):
        self.card['freshness_bound_hours'] = 0.5
        self.card['cost_bound'] = {'max_credits': 0, 'max_tokens': 0.0}
        self.assertTrue(verify_seal(seal_task_card(self.card, '2026-10-28T00:00:00Z')))

    def test_cli_nan_card_is_refused_before_chain_or_score(self):
        raw = json.loads(FIXTURE.read_text())
        raw['task_card']['freshness_bound_hours'] = float('nan')
        with tempfile.TemporaryDirectory() as tmp:
            path, chain = Path(tmp) / 'bad.json', Path(tmp) / 'chain.jsonl'
            path.write_text(json.dumps(raw))
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = cli.main(['run', '--pack', str(path), '--chain', str(chain)])
            self.assertEqual(rc, 1)
            self.assertFalse(chain.exists())
            self.assertNotIn('SCORECARD', out.getvalue())
            self.assertIn('finite', err.getvalue())


if __name__ == '__main__':
    unittest.main()
