"""Independent A5 criterion admission closure. Offline; writes temp evidence only."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scoring.sealing import seal_card

class IndependentCriterionChecks(unittest.TestCase):
    def setUp(self):
        self.pack = json.loads((ROOT / 'fixtures/synthetic_firecrawl.json').read_text())
        self.pack['human_decisions'] = []

    def test_nonfinite_and_boolean_bounds_are_rejected_before_seal(self):
        for location in ('card_freshness', 'question_freshness', 'max_credits', 'max_tokens'):
            for value in (float('nan'), float('inf'), float('-inf'), True, False):
                with self.subTest(location=location, value=repr(value)):
                    card = copy.deepcopy(self.pack['task_card'])
                    if location == 'card_freshness':
                        card['freshness_bound_hours'] = value
                    elif location == 'question_freshness':
                        card['questions'][0]['freshness_bound_hours'] = value
                    else:
                        card['cost_bound'][location] = value
                    with self.assertRaises(ValueError):
                        seal_card(card)

    def test_cli_nan_rejects_before_score_or_chain(self):
        self.pack['task_card']['freshness_bound_hours'] = float('nan')
        with tempfile.TemporaryDirectory(prefix='scoring-criterion-audit-') as tmp:
            pack_path = Path(tmp) / 'bad-pack.json'
            chain_path = Path(tmp) / 'chain.jsonl'
            pack_path.write_text(json.dumps(self.pack))
            proc = subprocess.run([sys.executable, '-m', 'scoring.cli', 'run', '--pack', str(pack_path), '--chain', str(chain_path)],
                                  cwd=ROOT, text=True, capture_output=True,
                                  env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse(chain_path.exists())
            self.assertNotIn('RUN SCORECARD', proc.stdout)
            self.assertIn('ERROR', proc.stderr)

if __name__ == '__main__':
    unittest.main(verbosity=2)
