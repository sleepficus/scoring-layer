"""Synthetic HTTP tests of the free-only capture/receipt boundary.

No test calls the Internet. Injected transports are visibly labeled synthetic
by the capture harness, preventing a passing mock from becoming live proof.
"""

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scoring.capture import load_fixture, load_task_pack, validate_run
from scoring.live import ENDPOINT, capture_live_task_pack, validate_live_capture


class CaptureCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plan = {
            "task_card": {
                "id": "synthetic-live-boundary-v1", "title": "SYNTHETIC mock HTTP test",
                "freshness_bound_hours": 1,
                "cost_bound": {"max_credits": 2, "max_tokens": 100},
                "questions": [{"id": "q1", "question": "What is the monthly price?",
                               "required_elements": ["$49 per month"]}],
            },
            "run_id": "mock-capture-v1", "agent_label": "synthetic-test-agent",
            "final_answer": "WidgetForge Pro costs $49 per month. [1]",
            "citations": {"1": "https://widgetforge.invalid/pricing"},
            "fetches": [{"url": "https://widgetforge.invalid/pricing",
                         "question_ids": ["q1"], "relied_on": True}],
        }
        self.plan_path = self.root / "plan.json"
        self.output = self.root / "capture.json"
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def response(self, *, status=200, body=None):
        if body is None:
            body = {"success": True, "data": {
                "markdown": "WidgetForge Pro costs $49 per month.",
                "metadata": {"sourceURL": "https://widgetforge.invalid/pricing",
                             "statusCode": 200}}}
        return {"status_code": status, "headers": {"Content-Type": "application/json",
                                                    "Retry-After": "60"},
                "body": json.dumps(body).encode("utf-8")}

    def capture(self, response=None, *, plan=None):
        self.plan_path.write_text(json.dumps(plan or self.plan), encoding="utf-8")
        def transport(request, timeout):
            self.calls.append((copy.deepcopy(request), timeout))
            return response or self.response()
        return capture_live_task_pack(self.plan_path, self.output, transport=transport)

    def test_mock_is_labeled_and_unknown_cost_is_not_zero(self):
        packet = self.capture()
        self.assertTrue(packet["synthetic"])
        self.assertEqual(packet["capture_receipts"][0]["transport"], "SYNTHETIC_TEST_TRANSPORT")
        fetch = packet["runs"][0]["fetches"][0]
        self.assertIsNone(fetch["creditsUsed"])
        self.assertIsNone(fetch["tokensUsed"])
        self.assertEqual(fetch["spend_status"], {"creditsUsed": "UNKNOWN", "tokensUsed": "UNKNOWN"})
        self.assertIsNone(packet["runs"][0]["agent_generation_tokens"])
        validate_live_capture(packet)
        loaded = load_task_pack(self.output)
        self.assertEqual(loaded["runs"][0]["fetches"], packet["runs"][0]["fetches"])

    def test_keyless_request_ignores_ambient_key_and_has_no_paid_options(self):
        with patch.dict(os.environ, {"FIRECRAWL_API_KEY": "not-a-real-key"}):
            self.capture()
        request, timeout = self.calls[0]
        self.assertEqual(request["url"], ENDPOINT)
        self.assertEqual(timeout, 45)
        self.assertFalse(any(k.lower() == "authorization" for k in request["headers"]))
        self.assertEqual(json.loads(request["body"]), {
            "url": "https://widgetforge.invalid/pricing", "formats": ["markdown"],
            "onlyMainContent": True})

    def test_api_key_is_refused_before_transport(self):
        self.plan_path.write_text(json.dumps(self.plan), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "keyless free"):
            capture_live_task_pack(self.plan_path, self.output,
                                   api_key="not-a-real-key", transport=lambda *a: self.fail())
        self.assertFalse(self.output.exists())

    def test_402_stops_and_preserves_body_without_retry(self):
        response = self.response(status=402, body={"success": False, "error": "quota exhausted"})
        packet = self.capture(response)
        self.assertEqual(packet["capture_status"], "BLOCKED")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(packet["capture_receipts"]), 1)
        self.assertEqual(packet["runs"], [])
        self.assertIn("no paid fallback", packet["capture_errors"][0]["error"])
        with self.assertRaisesRegex(ValueError, "BLOCKED"):
            load_task_pack(self.output)

    def test_429_stops_at_first_read_of_multi_page_plan(self):
        plan = copy.deepcopy(self.plan)
        plan["fetches"].append({**plan["fetches"][0], "url": "https://widgetforge.invalid/second"})
        packet = self.capture(self.response(status=429, body={"error": "daily keyless limit"}), plan=plan)
        self.assertEqual(packet["capture_status"], "BLOCKED")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(packet["capture_receipts"][0]["response_headers"]["retry-after"], "60")

    def test_output_is_write_once_before_any_duplicate_request(self):
        self.capture()
        before = self.output.read_bytes()
        with self.assertRaises(FileExistsError):
            self.capture()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.output.read_bytes(), before)

    def test_unsupported_paid_option_is_refused_before_request(self):
        plan = {**self.plan, "api_key": "not-a-real-key"}
        with self.assertRaisesRegex(ValueError, "unsupported"):
            self.capture(plan=plan)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.output.exists())

    def test_fetch_options_cannot_enable_extract_or_actions(self):
        plan = copy.deepcopy(self.plan)
        plan["fetches"][0]["formats"] = ["json"]
        with self.assertRaisesRegex(ValueError, "only url"):
            self.capture(plan=plan)
        self.assertEqual(self.calls, [])

    def test_unknown_question_refused_before_request(self):
        plan = copy.deepcopy(self.plan)
        plan["fetches"][0]["question_ids"] = ["unknown"]
        with self.assertRaisesRegex(ValueError, "sealed task card"):
            self.capture(plan=plan)
        self.assertEqual(self.calls, [])

    def test_credentials_in_target_url_refused_before_request(self):
        plan = copy.deepcopy(self.plan)
        plan["fetches"][0]["url"] = "https://secret:password@widgetforge.invalid/"
        with self.assertRaisesRegex(ValueError, "without credentials"):
            self.capture(plan=plan)
        self.assertEqual(self.calls, [])

    def test_provider_reported_metadata_spend_preserved_with_path(self):
        body = json.loads(self.response()["body"])
        body["data"]["metadata"].update(creditsUsed=1, tokensUsed=25)
        packet = self.capture(self.response(body=body))
        fetch = packet["runs"][0]["fetches"][0]
        self.assertEqual((fetch["creditsUsed"], fetch["tokensUsed"]), (1, 25))
        self.assertEqual(fetch["spend_sources"]["creditsUsed"], ["response.data.metadata.creditsUsed"])
        self.assertIn("agent generation tokens UNKNOWN", fetch["tokens_scope"])
        validate_live_capture(packet)

    def test_conflicting_provider_spend_rejected_with_raw_receipt(self):
        body = json.loads(self.response()["body"])
        body["creditsUsed"] = 1
        body["data"]["metadata"]["creditsUsed"] = 2
        packet = self.capture(self.response(body=body))
        self.assertEqual(packet["capture_status"], "INCOMPLETE")
        self.assertIn("conflicting provider creditsUsed", packet["capture_errors"][0]["error"])
        self.assertEqual(len(packet["capture_receipts"]), 1)

    def test_negative_provider_spend_rejected(self):
        body = json.loads(self.response()["body"])
        body["creditsUsed"] = -1
        packet = self.capture(self.response(body=body))
        self.assertEqual(packet["capture_status"], "INCOMPLETE")
        self.assertIn("non-negative", packet["capture_errors"][0]["error"])

    def test_provider_error_document_remains_fetch_truth_evidence(self):
        body = json.loads(self.response()["body"])
        body["data"]["metadata"]["statusCode"] = 403
        body["data"]["markdown"] = "# 403 Forbidden\nAccess denied."
        packet = self.capture(self.response(body=body))
        self.assertEqual(packet["capture_status"], "COMPLETE")
        self.assertEqual(packet["runs"][0]["fetches"][0]["statusCode"], 403)
        validate_live_capture(packet)

    def test_missing_markdown_preserves_raw_response_and_cannot_score(self):
        packet = self.capture(self.response(body={"success": True, "data": {"metadata": {}}}))
        self.assertEqual(packet["capture_status"], "INCOMPLETE")
        self.assertEqual(len(packet["capture_receipts"]), 1)
        with self.assertRaisesRegex(ValueError, "INCOMPLETE"):
            load_task_pack(self.output)

    def test_non_json_response_is_preserved(self):
        response = self.response()
        response["body"] = b"<html>gateway failure</html>"
        packet = self.capture(response)
        self.assertEqual(packet["capture_status"], "INCOMPLETE")
        self.assertIn("not JSON", packet["capture_errors"][0]["error"])
        self.assertEqual(packet["capture_receipts"][0]["response_bytes"], len(response["body"]))

    def test_transport_failure_is_recorded_without_retry(self):
        self.plan_path.write_text(json.dumps(self.plan), encoding="utf-8")
        def transport(*args):
            self.calls.append(args)
            raise TimeoutError("synthetic transport timeout")
        packet = capture_live_task_pack(self.plan_path, self.output, transport=transport)
        self.assertEqual(packet["capture_status"], "INCOMPLETE")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(packet["capture_receipts"]), 1)
        attempt = packet["capture_receipts"][0]
        self.assertEqual(attempt["outcome"], "TRANSPORT_ERROR")
        self.assertIsNone(attempt["response_sha256"])
        self.assertIsNone(attempt["http_status"])
        self.assertEqual(len(attempt["request_sha256"]), 64)
        self.assertIn("timeout", packet["capture_errors"][0]["error"])

    def test_response_bytes_tamper_detected(self):
        packet = self.capture()
        packet["capture_receipts"][0]["response_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash/size mismatch"):
            validate_live_capture(packet)

    def test_normalized_content_tamper_detected_even_when_raw_hash_valid(self):
        packet = self.capture()
        packet["runs"][0]["fetches"][0]["content_markdown"] = "WidgetForge costs $1."
        with self.assertRaisesRegex(ValueError, "differs from captured provider response"):
            validate_live_capture(packet)

    def test_request_tamper_detected(self):
        packet = self.capture()
        packet["capture_receipts"][0]["request_headers"]["Authorization"] = "Bearer synthetic"
        with self.assertRaisesRegex(ValueError, "headers changed"):
            validate_live_capture(packet)

    def test_fake_live_label_on_mock_receipt_detected(self):
        packet = self.capture()
        packet["synthetic"] = False
        packet["runs"][0]["synthetic"] = False
        with self.assertRaisesRegex(ValueError, "origin mismatch"):
            validate_live_capture(packet)

    def test_changed_final_answer_requires_new_captured_plan(self):
        packet = self.capture()
        packet["runs"][0]["final_answer"] = "WidgetForge costs $1."
        with self.assertRaisesRegex(ValueError, "identity/answer differs"):
            validate_live_capture(packet)

    def test_citation_changes_omissions_and_additions_are_rejected(self):
        packet = self.capture()
        changed = copy.deepcopy(packet)
        changed["runs"][0]["citations"] = {"1": "https://widgetforge.invalid/forged"}
        omitted = copy.deepcopy(packet)
        omitted["runs"][0].pop("citations")
        with self.subTest("changed"):
            with self.assertRaisesRegex(ValueError, "run citations differs"):
                validate_live_capture(changed)
        with self.subTest("omitted"):
            with self.assertRaisesRegex(ValueError, "run citations differs"):
                validate_live_capture(omitted)
        self.output.unlink()
        plan = copy.deepcopy(self.plan)
        plan.pop("citations")
        added = self.capture(plan=plan)
        added["runs"][0]["citations"] = None
        with self.subTest("added null is not absence"):
            with self.assertRaisesRegex(ValueError, "run citations differs"):
                validate_live_capture(added)

    def test_judge_changes_omissions_and_additions_are_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["judge_decisions"] = []
        packet = self.capture(plan=plan)
        validate_live_capture(packet)
        for value in ([{"claim_id": "forged"}], None):
            changed = copy.deepcopy(packet)
            changed["runs"][0]["judge_decisions"] = value
            with self.subTest(changed=value):
                with self.assertRaisesRegex(ValueError, "run judge_decisions differs"):
                    validate_live_capture(changed)
        omitted = copy.deepcopy(packet)
        omitted["runs"][0].pop("judge_decisions")
        with self.assertRaisesRegex(ValueError, "run judge_decisions differs"):
            validate_live_capture(omitted)
        self.output.unlink()
        added = self.capture()
        added["runs"][0]["judge_decisions"] = []
        with self.assertRaisesRegex(ValueError, "run judge_decisions differs"):
            validate_live_capture(added)

    def test_run_start_and_card_seal_time_must_equal_original_capture_start(self):
        packet = self.capture()
        for target, key in (("run", "started_at"), ("sealed", "sealed_at"),
                            ("packet", "capture_started_at")):
            changed = copy.deepcopy(packet)
            holder = (changed["runs"][0] if target == "run" else
                      changed["sealed_task_card"] if target == "sealed" else changed)
            holder[key] = "1999-01-01T00:00:00Z"
            with self.subTest(target=target):
                with self.assertRaisesRegex(ValueError, "start timestamps differ"):
                    validate_live_capture(changed)

    def test_missing_start_and_naive_capture_timestamps_are_rejected(self):
        packet = self.capture()
        missing = copy.deepcopy(packet)
        missing["runs"][0].pop("started_at")
        with self.assertRaisesRegex(ValueError, "started_at"):
            validate_live_capture(missing)
        naive = copy.deepcopy(packet)
        for holder, name in ((naive, "capture_started_at"),
                             (naive["runs"][0], "started_at"),
                             (naive["sealed_task_card"], "sealed_at")):
            holder[name] = "2026-10-28T12:00:00"
        with self.assertRaisesRegex(ValueError, "aware ISO-8601"):
            validate_live_capture(naive)

    def test_response_clock_outside_capture_interval_is_rejected(self):
        packet = self.capture()
        for edit in (lambda p: p["capture_receipts"][0].update(started_at="1999-01-01T00:00:00Z"),
                     lambda p: p["capture_receipts"][0].update(finished_at="2999-01-01T00:00:00Z"),
                     lambda p: p.update(capture_finished_at="1999-01-01T00:00:00Z")):
            changed = copy.deepcopy(packet)
            edit(changed)
            with self.assertRaisesRegex(ValueError, "timestamps"):
                validate_live_capture(changed)

    def test_strict_validation_still_rejects_missing_fixture_spend(self):
        fixture_path = Path(__file__).resolve().parent.parent / "fixtures/synthetic_firecrawl.json"
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        del raw["runs"][0]["fetches"][0]["response"]["creditsUsed"]
        self.plan_path.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "missing required spend"):
            load_fixture(self.plan_path)

    def test_unknown_spend_needs_explicit_capture_validation(self):
        packet = self.capture()
        with self.assertRaisesRegex(ValueError, "must be a number"):
            validate_run(packet["runs"][0])
        validate_run(packet["runs"][0], allow_unknown_spend=True)


if __name__ == "__main__":
    unittest.main()
