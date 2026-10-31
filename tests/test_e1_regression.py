"""Regression tests for external-audit finding E1 (LOW).

Citation-adjacent punctuation (a comma or parentheses hugging a citation
token) survived claim normalization and defeated the narrow assertion
matcher, so claims whose cited passage supports them exactly were graded
UNSUPPORTED. These tests are named for the finding. The SUPPORTED cases
fail on the pre-fix code and pass after the normalization repair; the
control cases pin the fail-closed direction on both versions.
"""
import unittest

from scoring.claims import grade_claim_support

URL = "https://example.invalid/pricing"
LIMITS_URL = "https://example.invalid/limits"


def run(answer, content="Acme Pro includes 500 requests.", **extra):
    result = {"run_id": "r1", "final_answer": answer, "claims": [],
              "fetches": [{"url": URL, "statusCode": 200,
                           "content_markdown": content}]}
    result.update(extra)
    return result


def verdicts(record):
    return [c["verdict"] for c in grade_claim_support(record)["claims"]]


class TestE1CitationPunctuation(unittest.TestCase):
    def test_e1_citation_comma_still_supported(self):
        record = run("Acme Pro includes 500 requests [1], and provides 24/7 support.",
                     citations={"1": URL})
        self.assertEqual(verdicts(record)[0], "SUPPORTED")

    def test_e1_parenthesized_citation_still_supported(self):
        record = run("Acme Pro includes 500 requests ([1]).", citations={"1": URL})
        self.assertEqual(verdicts(record), ["SUPPORTED"])

    def test_e1_citation_comma_price_still_supported(self):
        record = run(
            "WidgetForge Pro costs $49 per month [1], and includes 1200 requests per month [1].",
            content="WidgetForge Pro costs $49 per month. "
                    "WidgetForge Pro includes 1200 requests per month.",
            citations={"1": URL})
        self.assertEqual(verdicts(record), ["SUPPORTED", "SUPPORTED"])

    def test_e1_parenthesized_citation_after_subject_still_supported(self):
        record = run("Acme Pro ([1]) includes 500 requests.", citations={"1": URL})
        self.assertEqual(verdicts(record), ["SUPPORTED"])

    def test_e1_parenthesized_citation_exact_statement_supported(self):
        # Support here can only come from complete-statement equality:
        # "is based in" matches no narrow scalar assertion pattern.
        record = run("Acme Pro is based in Denver ([1]).",
                     content="Acme Pro is based in Denver.",
                     citations={"1": URL})
        self.assertEqual(verdicts(record), ["SUPPORTED"])

    def test_e1_citation_comma_but_clause_still_supported(self):
        record = run("Acme Pro includes 500 requests [1], but costs $10 per month.",
                     content="Acme Pro includes 500 requests. Acme Pro costs $10 per month.",
                     citations={"1": URL})
        self.assertEqual(verdicts(record)[0], "SUPPORTED")

    def test_e1_thousands_comma_inside_value_untouched(self):
        # The digit-grouping comma inside "1,200" is content, not residue;
        # the citation-hugging comma after [1] must still be repaired.
        record = run(
            "WidgetForge Pro includes 1,200 requests per month [1], and costs $49 per month [1].",
            content="WidgetForge Pro includes 1200 requests per month. "
                    "WidgetForge Pro costs $49 per month.",
            citations={"1": URL})
        self.assertEqual(verdicts(record), ["SUPPORTED", "SUPPORTED"])

    def test_e1_unsupported_claim_with_citation_comma_stays_unsupported(self):
        # Control: same punctuation shape, but the cited passage is about a
        # different subject. The repair must not invent support.
        record = run("Acme Pro includes 500 requests [1], and provides 24/7 support.",
                     content="OtherCo includes 500 requests.",
                     citations={"1": URL})
        self.assertEqual(verdicts(record)[0], "UNSUPPORTED")

    def test_e1_citation_comma_different_value_is_contradicted(self):
        # Same shape, same subject/relation/unit, different value: the
        # repaired normalization lets the contradiction branch see the
        # assertion. This never routes through SUPPORTED.
        record = run("Acme Pro includes 900 requests [1], and provides 24/7 support.",
                     citations={"1": URL})
        self.assertEqual(verdicts(record)[0], "CONTRADICTED")

    def test_e1_separately_cited_clauses_with_commas_do_not_borrow(self):
        record = run(
            "WidgetForge Pro costs $49 per month [1], and includes 1200 requests per month [2].",
            content="WidgetForge Pro costs $49 per month.",
            citations={"1": URL, "2": LIMITS_URL})
        record["fetches"].append(
            {"url": LIMITS_URL, "statusCode": 200,
             "content_markdown": "WidgetForge Pro includes 1200 requests per month."})
        result = grade_claim_support(record)
        self.assertEqual([c["verdict"] for c in result["claims"]],
                         ["SUPPORTED", "SUPPORTED"])
        self.assertEqual([c["url"] for c in result["claims"][0]["citations"]], [URL])
        self.assertEqual([c["url"] for c in result["claims"][1]["citations"]], [LIMITS_URL])

    def test_e1_parenthesized_unit_context_not_erased(self):
        # Guard against over-stripping: non-empty parentheses are claim
        # content (a unit context) and must survive normalization.
        record = run("Acme Pro includes 500 requests (per month) [1].",
                     content="Acme Pro includes 500 requests (per month).",
                     citations={"1": URL})
        self.assertEqual(verdicts(record), ["SUPPORTED"])
        self.assertEqual(
            grade_claim_support(record)["claims"][0]["normalized_claim"],
            "Acme Pro includes 500 requests (per month)")


if __name__ == "__main__":
    unittest.main()
