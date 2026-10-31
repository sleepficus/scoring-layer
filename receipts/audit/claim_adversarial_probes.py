"""Independent Session 2 claim probes. Offline; no builder-code changes.

Run from candidate root:
    python3.12 receipts/audit/claim_adversarial_probes.py
"""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scoring.claims import grade_claim_support

URL = 'https://audit.invalid/pricing'


def record(answer, source):
    return {'run_id': 'independent-audit', 'final_answer': answer, 'claims': [],
            'citations': {'1': URL},
            'fetches': [{'url': URL, 'statusCode': 200, 'content_markdown': source}]}


def grade(answer, source):
    return grade_claim_support(record(answer, source))


class IndependentClaimChecks(unittest.TestCase):
    def test_exact_cited_support_control(self):
        row = grade('WidgetForge Pro costs $49 per month [1].',
                    'WidgetForge Pro costs $49 per month.')['claims'][0]
        self.assertEqual(row['verdict'], 'SUPPORTED')
        self.assertEqual(row['passages'][0]['text'], 'WidgetForge Pro costs $49 per month.')

    def test_different_value_contradiction_control(self):
        row = grade('WidgetForge Pro costs $99 per month [1].',
                    'WidgetForge Pro costs $49 per month.')['claims'][0]
        self.assertEqual(row['verdict'], 'CONTRADICTED')

    def test_uncited_statement_control(self):
        row = grade('WidgetForge Pro costs $49 per month.',
                    'WidgetForge Pro costs $49 per month.')['claims'][0]
        self.assertEqual(row['verdict'], 'UNSUPPORTED')
        self.assertEqual(row['citations'], [])

    def test_qualified_inline_source_control(self):
        row = grade('WidgetForge Pro costs $49 per month [1].',
                    'WidgetForge Pro costs $49 per month if billed annually.')['claims'][0]
        self.assertNotEqual(row['verdict'], 'SUPPORTED')

    def test_a1_postsentence_reference_does_not_bind_following_uncited_sentence(self):
        result = grade('WidgetForge Pro costs $49 per month. [1] WidgetForge Pro includes 1200 requests per month.',
                       'WidgetForge Pro costs $49 per month. WidgetForge Pro includes 1200 requests per month.')
        self.assertEqual(len(result['claims']), 2)
        self.assertEqual(result['claims'][0]['verdict'], 'SUPPORTED')
        self.assertEqual(result['claims'][1]['citations'], [],
                         'The [1] after the first full stop must not also bind the second sentence.')
        self.assertEqual(result['claims'][1]['verdict'], 'UNSUPPORTED')

    def test_a2_equal_decimal_price_is_not_contradiction(self):
        for source_value, claim_value in [('49.00', '49'), ('49', '49.0'), ('1,200.00', '1200')]:
            with self.subTest(source=source_value, claim=claim_value):
                row = grade(f'WidgetForge Pro costs ${claim_value} per month [1].',
                            f'WidgetForge Pro costs ${source_value} per month.')['claims'][0]
                self.assertEqual(row['verdict'], 'SUPPORTED')

    def test_a3_factual_markdown_heading_is_measured(self):
        result = grade('# WidgetForge Pro costs $49 per month [1]',
                       'WidgetForge Pro costs $49 per month.')
        self.assertEqual(result['deterministic']['total'], 1,
                         'A straightforward factual assertion cannot disappear merely because it is a Markdown heading.')

    def test_a4_source_qualification_markers_are_not_erased_into_support(self):
        for source in ['WidgetForge Pro costs $49 per month.*\n*Only if billed annually.',
                       'WidgetForge Pro costs $49 per month [2024].']:
            with self.subTest(source=source):
                row = grade('WidgetForge Pro costs $49 per month [1].', source)['claims'][0]
                self.assertNotEqual(row['verdict'], 'SUPPORTED',
                                    'Source numeric brackets/footnotes carry source meaning unless explicitly resolved.')

    def test_judge_invented_passage_control(self):
        run = record('WidgetForge Pro costs $49 monthly [1].', 'WidgetForge Pro costs $49 per month.')
        decision = {'claim_id': 'independent-audit:claim:1', 'verdict': 'SUPPORTED',
                    'judge': {'seat': 'independent-probe', 'model': 'synthetic-data', 'reviewed_at': '2026-10-28T04:30:00Z'},
                    'reasoning': 'probe', 'passages': [{'fetch_index': 0, 'start': 0, 'end': 8, 'text': 'invented'}]}
        with self.assertRaises(ValueError):
            grade_claim_support(run, [decision])


if __name__ == '__main__':
    unittest.main(verbosity=2)
