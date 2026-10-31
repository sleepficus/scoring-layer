"""Behavioral tests for captured citation binding, conservative support and judge receipts."""
import copy
import unittest

from scoring.claims import extract_claims, grade_claim_support, populate_claims

URL = "https://example.invalid/pricing"


def run(answer, content="WidgetForge Pro costs $49 per month.", **extra):
    result = {"run_id": "r1", "final_answer": answer, "claims": [],
              "fetches": [{"url": URL, "statusCode": 200,
                           "content_markdown": content}]}
    result.update(extra)
    return result


def verdict(record):
    return grade_claim_support(record)["claims"][0]


class TestExtraction(unittest.TestCase):
    def test_exact_spans_and_stable_ids(self):
        record = run("WidgetForge Pro costs $49 per month [1].", citations={"1": URL})
        a = extract_claims(record)
        self.assertEqual(a, extract_claims(record))
        self.assertEqual(a[0]["claim_id"], "r1:claim:1")
        s = a[0]["answer_span"]
        self.assertEqual(a[0]["text"], record["final_answer"][s["start"]:s["end"]])

    def test_compound_claim_inherits_subject_with_raw_span_intact(self):
        record = run("WidgetForge Pro costs $49 per month and includes 1200 requests per month [1].", citations={"1": URL})
        claims = extract_claims(record)
        self.assertEqual(len(claims), 2)
        self.assertEqual(claims[1]["normalized_claim"], "WidgetForge Pro includes 1200 requests per month")
        self.assertTrue(claims[1]["text"].startswith("includes"))
        self.assertEqual(claims[1]["context_prefix"], "WidgetForge Pro ")

    def test_separately_cited_clauses_do_not_borrow_sources(self):
        second_url = "https://example.invalid/limits"
        record = run("WidgetForge Pro costs $49 per month [1] and includes 1200 requests per month [2].",
                     citations={"1": URL, "2": second_url})
        record["fetches"].append({"url": second_url, "statusCode": 200,
                                  "content_markdown": "WidgetForge Pro includes 1200 requests per month."})
        claims = extract_claims(record)
        self.assertEqual([c["url"] for c in claims[0]["citations"]], [URL])
        self.assertEqual([c["url"] for c in claims[1]["citations"]], [second_url])
        self.assertEqual(grade_claim_support(record)["deterministic"]["SUPPORTED"], 2)

    def test_later_uncited_clause_does_not_inherit_earlier_citation(self):
        record = run("WidgetForge Pro costs $49 per month [1] and includes 1200 requests per month.", citations={"1": URL})
        claims = extract_claims(record)
        self.assertEqual(claims[1]["citations"], [])

    def test_does_not_split_decimal_or_url(self):
        claims = extract_claims(run("Pro costs $4.99 per month [source](https://example.invalid/pricing)."))
        self.assertEqual(len(claims), 1)
        self.assertIn("$4.99", claims[0]["text"])

    def test_reference_definitions_do_not_become_claims(self):
        record = run("WidgetForge Pro costs $49 per month [p].\n\n[p]: " + URL)
        self.assertEqual(len(extract_claims(record)), 1)
        self.assertEqual(verdict(record)["verdict"], "SUPPORTED")

    def test_citation_after_period_attaches(self):
        record = run("WidgetForge Pro costs $49 per month. [1]", citations={"1": URL})
        self.assertEqual(verdict(record)["verdict"], "SUPPORTED")
        self.assertEqual(len(extract_claims(record)), 1)

    def test_supplied_claim_list_cannot_hide_answer(self):
        record = run("WidgetForge Pro costs $49 per month [1].", citations={"1": URL}, claims=[{"verdict": "SUPPORTED", "text": "fake"}])
        populate_claims(record)
        self.assertNotEqual(record["claims"][0]["text"], "fake")
        self.assertTrue(record["claim_extraction"]["limits"])

    def test_empty_answer_has_zero_measured_claims(self):
        result = grade_claim_support(run(""))
        self.assertEqual(result["deterministic"]["total"], 0)
        self.assertEqual(result["claims"], [])

    def test_unknown_claim_citation_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown claim"):
            extract_claims(run("A costs $1 per month.", claim_citations={"other": URL}))


class TestBindingAndSupport(unittest.TestCase):
    def test_exact_support_has_actual_offsets_and_hash(self):
        record = run("WidgetForge Pro costs $49 per month [1].", citations={"1": URL})
        row = verdict(record)
        self.assertEqual(row["verdict"], "SUPPORTED")
        passage = row["passages"][0]
        self.assertEqual(passage["text"], record["fetches"][0]["content_markdown"][passage["start"]:passage["end"]])
        self.assertEqual(len(passage["document_sha256"]), 64)
        self.assertEqual(passage["url"], URL)

    def test_inline_link(self):
        row = verdict(run("WidgetForge Pro costs $49 per month [source](" + URL + ")."))
        self.assertEqual(row["verdict"], "SUPPORTED")

    def test_uncited_legacy_answer_is_not_inferred_from_fetch(self):
        record = run("WidgetForge Pro costs $49 per month.")
        record["fetches"][0].update(relied_on=True, question_ids=["q1"])
        row = verdict(record)
        self.assertEqual(row["verdict"], "UNSUPPORTED")
        self.assertIn("No cited evidence", row["absence"])
        self.assertFalse(row["needs_judge"])

    def test_unfetched_citation_does_not_borrow_other_source(self):
        row = verdict(run("WidgetForge Pro costs $49 per month [1].", citations={"1": "https://not-fetched.invalid"}))
        self.assertEqual(row["verdict"], "UNSUPPORTED")
        self.assertIn("not fetched", row["binding_errors"][0])

    def test_unknown_reference_is_recorded(self):
        row = verdict(run("WidgetForge Pro costs $49 per month [9]."))
        self.assertEqual(row["verdict"], "UNSUPPORTED")
        self.assertIn("unresolved", row["binding_errors"][0])

    def test_fragment_binds_same_document_query_does_not(self):
        record = run("WidgetForge Pro costs $49 per month [1].", citations={"1": URL + "#pro"})
        self.assertEqual(verdict(record)["verdict"], "SUPPORTED")
        record["citations"]["1"] = URL + "?version=other"
        self.assertEqual(verdict(record)["verdict"], "UNSUPPORTED")

    def test_error_response_cannot_support(self):
        record = run("WidgetForge Pro costs $49 per month [1].", citations={"1": URL})
        record["fetches"][0]["statusCode"] = 403
        self.assertEqual(verdict(record)["verdict"], "UNSUPPORTED")

    def test_different_scalar_value_is_contradicted(self):
        record = run("WidgetForge Pro costs $99 per month [1].", citations={"1": URL})
        row = verdict(record)
        self.assertEqual(row["verdict"], "CONTRADICTED")
        self.assertIn("$49", row["passages"][0]["text"])

    def test_other_subject_does_not_contradict_or_support(self):
        record = run("OtherCo Pro costs $49 per month [1].", citations={"1": URL})
        self.assertEqual(verdict(record)["verdict"], "UNSUPPORTED")

    def test_negated_or_qualified_source_does_not_support(self):
        for source in ("WidgetForge Pro does not cost $49 per month.",
                       "WidgetForge Pro costs $49 per month if paid annually.",
                       "OtherCo claims WidgetForge Pro costs $49 per month.",
                       "It is false that WidgetForge Pro costs $49 per month.",
                       "WidgetForge Pro costs $49 per month [only if paid annually]."):
            with self.subTest(source=source):
                self.assertEqual(verdict(run("WidgetForge Pro costs $49 per month [1].", source, citations={"1": URL}))["verdict"], "UNSUPPORTED")

    def test_comma_number_variant_matches(self):
        record = run("WidgetForge Pro includes 1,200 requests per month [1].",
                     "WidgetForge Pro includes 1200 requests per month.", citations={"1": URL})
        self.assertEqual(verdict(record)["verdict"], "SUPPORTED")

    def test_paraphrase_is_honest_semantic_residue(self):
        row = verdict(run("WidgetForge Pro costs $49 monthly [1].", citations={"1": URL}))
        self.assertEqual(row["verdict"], "UNSUPPORTED")
        self.assertTrue(row["needs_judge"])
        self.assertIn("Semantic entailment remains unmeasured", row["absence"])

    def test_conflicting_cited_documents_are_explicit(self):
        record = run("WidgetForge Pro costs $49 per month [1].", citations={"1": URL})
        record["fetches"].append({"url": URL, "statusCode": 200, "content_markdown": "WidgetForge Pro costs $99 per month."})
        row = verdict(record)
        self.assertEqual(row["verdict"], "CONTRADICTED")
        self.assertTrue(row["needs_judge"])
        self.assertEqual(len(row["passages"]), 2)

    def test_capture_attribution_map_is_data_only(self):
        record = run("WidgetForge Pro costs $49 per month.", claim_citations={"r1:claim:1": URL})
        self.assertEqual(verdict(record)["verdict"], "SUPPORTED")
        self.assertEqual(verdict(record)["citations"][0]["reference"], "captured claim_citations")


class TestAuditRepairs(unittest.TestCase):
    """Regression coverage for independently reported A1–A4, not altered audit probes."""

    def test_a1_postsentence_citation_is_consumed_before_next_sentence(self):
        record = run("WidgetForge Pro costs $49 per month. [1] WidgetForge Pro includes 1200 requests per month.",
                     "WidgetForge Pro costs $49 per month. WidgetForge Pro includes 1200 requests per month.",
                     citations={"1": URL})
        rows = grade_claim_support(record)["claims"]
        self.assertEqual([r["verdict"] for r in rows], ["SUPPORTED", "UNSUPPORTED"])
        self.assertEqual(rows[1]["citations"], [])
        span = rows[1]["answer_span"]
        self.assertEqual(rows[1]["text"], record["final_answer"][span["start"]:span["end"]])
        self.assertNotIn("[1]", rows[1]["text"])

    def test_a1_following_sentence_keeps_its_own_citation(self):
        other_url = "https://example.invalid/limits"
        record = run("WidgetForge Pro costs $49 per month. [1] WidgetForge Pro includes 1200 requests per month [2].",
                     citations={"1": URL, "2": other_url})
        record["fetches"].append({"url": other_url, "statusCode": 200,
                                  "content_markdown": "WidgetForge Pro includes 1200 requests per month."})
        rows = grade_claim_support(record)["claims"]
        self.assertEqual([r["verdict"] for r in rows], ["SUPPORTED", "SUPPORTED"])
        self.assertEqual([c["url"] for c in rows[1]["citations"]], [other_url])

    def test_a2_decimal_equivalence_is_exact_and_retains_source_spelling(self):
        for source, claimed in [("49.00", "49"), ("49", "49.0"), ("1,200.00", "1200")]:
            with self.subTest(source=source, claimed=claimed):
                row = verdict(run(f"WidgetForge Pro costs ${claimed} per month [1].",
                                  f"WidgetForge Pro costs ${source} per month.", citations={"1": URL}))
                self.assertEqual(row["verdict"], "SUPPORTED")
                self.assertIn("$" + source, row["passages"][0]["text"])
        row = verdict(run("WidgetForge Pro costs $49.000000000000000001 per month [1].",
                          "WidgetForge Pro costs $49.000000000000000002 per month.", citations={"1": URL}))
        self.assertEqual(row["verdict"], "CONTRADICTED")

    def test_a2_equal_request_decimal_is_supported(self):
        row = verdict(run("WidgetForge Pro includes 1200 requests per month [1].",
                          "WidgetForge Pro includes 1,200.00 requests per month.", citations={"1": URL}))
        self.assertEqual(row["verdict"], "SUPPORTED")

    def test_a3_factual_heading_has_exact_text_span(self):
        record = run("## WidgetForge Pro costs $49 per month [1]", citations={"1": URL})
        result = grade_claim_support(record)
        self.assertEqual(result["deterministic"]["total"], 1)
        self.assertEqual(result["claims"][0]["verdict"], "SUPPORTED")
        span = result["claims"][0]["answer_span"]
        self.assertEqual(result["claims"][0]["text"], record["final_answer"][span["start"]:span["end"]])
        self.assertEqual(grade_claim_support(run("# Overview"))["deterministic"]["total"], 0)

    def test_a4_source_footnote_and_numeric_brackets_are_semantic_residue(self):
        for source in ("WidgetForge Pro costs $49 per month.*\n*Only if billed annually.",
                       "WidgetForge Pro costs $49 per month. *\n*Only if billed annually.",
                       "WidgetForge Pro costs $49 per month. [2024]",
                       "WidgetForge Pro costs $49 per month [2024].",
                       "WidgetForge Pro includes 1200 requests per month [2024]."):
            with self.subTest(source=source):
                claim = "WidgetForge Pro includes 1200 requests per month [1]." if "includes" in source else "WidgetForge Pro costs $49 per month [1]."
                row = verdict(run(claim, source, citations={"1": URL}))
                self.assertEqual(row["verdict"], "UNSUPPORTED")
                self.assertTrue(row["needs_judge"])
                self.assertIn("markers remain unresolved", row["reason"])
                self.assertTrue(row["qualification_passages"])
                for passage in row["qualification_passages"]:
                    self.assertEqual(passage["text"], source[passage["start"]:passage["end"]])


class TestJudge(unittest.TestCase):
    def setUp(self):
        self.record = run("WidgetForge Pro costs $49 monthly [1].", citations={"1": URL})
        content = self.record["fetches"][0]["content_markdown"]
        self.decision = {"claim_id": "r1:claim:1", "verdict": "SUPPORTED",
                         "judge": {"seat": "external-test-seat", "model": "synthetic-judge", "reviewed_at": "2026-10-28T04:00:00Z"},
                         "reasoning": "Monthly expresses per month.",
                         "passages": [{"fetch_index": 0, "start": 0, "end": len(content), "text": content}]}

    def test_judge_counts_never_replace_deterministic(self):
        result = grade_claim_support(self.record, [self.decision])
        self.assertEqual(result["deterministic"]["UNSUPPORTED"], 1)
        self.assertEqual(result["judge"]["SUPPORTED"], 1)
        self.assertEqual(result["claims"][0]["method"], "DETERMINISTIC")
        self.assertEqual(result["judge_claims"][0]["method"], "JUDGE")
        self.assertEqual(result["flag_count"], 1)

    def test_invented_passage_rejected(self):
        self.decision["passages"][0]["text"] = "invented"
        with self.assertRaisesRegex(ValueError, "captured"):
            grade_claim_support(self.record, [self.decision])

    def test_uncited_passage_rejected(self):
        self.record["fetches"].append({"url": "https://other.invalid", "statusCode": 200, "content_markdown": "X"})
        self.decision["passages"] = [{"fetch_index": 1, "start": 0, "end": 1, "text": "X"}]
        with self.assertRaisesRegex(ValueError, "bound fetch"):
            grade_claim_support(self.record, [self.decision])

    def test_supported_without_passage_rejected(self):
        self.decision["passages"] = []
        with self.assertRaisesRegex(ValueError, "requires a captured passage"):
            grade_claim_support(self.record, [self.decision])

    def test_unsupported_requires_absence(self):
        self.decision.update(verdict="UNSUPPORTED", passages=[])
        with self.assertRaisesRegex(ValueError, "absence"):
            grade_claim_support(self.record, [self.decision])
        self.decision["absence"] = "No supporting passage after manual review."
        result = grade_claim_support(self.record, [self.decision])
        self.assertEqual(result["judge"]["UNSUPPORTED"], 1)
        self.assertEqual(result["flags"][-1]["grader"], "claim-support-judge")

    def test_duplicate_or_unknown_judge_claim_rejected(self):
        for decisions in ([self.decision, self.decision], [{**self.decision, "claim_id": "fake"}]):
            with self.assertRaises(ValueError): grade_claim_support(self.record, decisions)

    def test_missing_provenance_rejected(self):
        self.decision["judge"] = {}
        with self.assertRaisesRegex(ValueError, "provenance"):
            grade_claim_support(self.record, [self.decision])

    def test_cannot_judge_deterministic_exact_support(self):
        self.record["final_answer"] = "WidgetForge Pro costs $49 per month [1]."
        with self.assertRaisesRegex(ValueError, "residue"):
            grade_claim_support(self.record, [self.decision])


if __name__ == "__main__":
    unittest.main()
