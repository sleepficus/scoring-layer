"""Independent offline audit probes; no source edits, network or new capture.

Run from the project root with:
PYTHONDONTWRITEBYTECODE=1 python3.12 receipts/audit/helper-capture-chain-probe.py
All mutations are copies of supplied evidence under this audit's helper paths.
"""
from __future__ import annotations

import base64
import contextlib
import copy
import hashlib
import io
import json
import math
import platform
import socket
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scoring import cli
from scoring.capture import load_fixture, load_task_pack
from scoring.chain import Store
from scoring.graders import grade_run, grade_session2_run
from scoring.live import normalize_live_fetch, validate_live_capture
from scoring.precision import compute_precision, decisions_from_chain
from scoring.scorecard import render_precision
from scoring.sealing import seal_task_card, verify_seal

AUDIT = ROOT / "receipts/audit"
RESULTS = AUDIT / "helper-capture-chain-results.json"


def no_network(*args, **kwargs):
    raise AssertionError("Audit forbids network access")


socket.create_connection = no_network
socket.socket.connect = no_network


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n")


checks = []
findings = []


def check(name, assertion, details=None):
    checks.append({"name": name, "pass": bool(assertion), "details": details})
    return bool(assertion)


def rejects(name, fn, phrase=None):
    try:
        fn()
    except (ValueError, TypeError, KeyError) as exc:
        return check(name, phrase is None or phrase in str(exc),
                     {"exception": type(exc).__name__, "message": str(exc)})
    return check(name, False, "Unexpectedly accepted")


def main_call(argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        rc = cli.main(argv)
    return {"argv": argv, "exit": rc, "stdout": stdout.getvalue(), "stderr": stderr.getvalue()}


inputs = [*sorted((ROOT / "scoring").glob("*.py")),
          ROOT / "data/chain.jsonl", ROOT / "fixtures/synthetic_firecrawl.json",
          ROOT / "receipts/live-keyless-capture.json"]
before = {str(p.relative_to(ROOT)): sha(p) for p in inputs}
packet = json.loads((ROOT / "receipts/live-keyless-capture.json").read_text())
loaded_live = load_task_pack(ROOT / "receipts/live-keyless-capture.json")
validate_live_capture(packet)
check("recorded-live-complete-validation", packet["synthetic"] is False and packet["capture_status"] == "COMPLETE")
live_details = {
    "file_sha256": sha(ROOT / "receipts/live-keyless-capture.json"),
    "capture_started_at": packet["capture_started_at"],
    "capture_finished_at": packet["capture_finished_at"],
    "free_tier": packet["free_tier"],
    "receipts": [{k: r[k] for k in ("transport", "outcome", "requested_url", "request_url", "http_status", "response_sha256", "response_bytes")}
                 for r in packet["capture_receipts"]],
    "spend": [{k: f[k] for k in ("creditsUsed", "tokensUsed", "spend_status", "spend_sources", "tokens_scope")}
              for f in packet["runs"][0]["fetches"]],
}
for receipt in packet["capture_receipts"]:
    body = base64.b64decode(receipt["response_body_base64"], validate=True)
    check("raw-response-byte-hash-and-size", digest(body) == receipt["response_sha256"] and len(body) == receipt["response_bytes"])
    check("recorded-request-has-no-authorization", not any(k.lower() == "authorization" for k in receipt["request_headers"]))
    check("recorded-request-fixed-read-options", json.loads(receipt["request_body"]) == {"url": receipt["requested_url"], "formats": ["markdown"], "onlyMainContent": True})
grade = grade_session2_run(copy.deepcopy(loaded_live["runs"][0]), loaded_live["task_card"])
cost = grade["dimensions"]["Cost truth"]["cost"]
check("live-missing-tokens-remain-unknown", cost["total_tokens"] is None and cost["tokens_per_verified_fact"] is None)
check("live-unknown-token-cost-is-unverifiable", any(f["evidence"].get("status") == "UNVERIFIABLE" and "tokens" in f["evidence"].get("unknown_units", []) for f in grade["dimensions"]["Cost truth"]["flags"]))

mutations = [
    ("blocked-packet", lambda p: p.update(capture_status="BLOCKED"), "cannot score"),
    ("incomplete-packet", lambda p: p.update(capture_status="INCOMPLETE"), "cannot score"),
    ("error-bearing-complete-packet", lambda p: p.update(capture_errors=["probe"]), "cannot score"),
    ("response-hash-tamper", lambda p: p["capture_receipts"][0].update(response_sha256="0" * 64), "hash/size mismatch"),
    ("response-size-tamper", lambda p: p["capture_receipts"][0].update(response_bytes=1), "hash/size mismatch"),
    ("normalized-markdown-tamper", lambda p: p["runs"][0]["fetches"][0].update(content_markdown="Forged text"), "differs from captured provider response"),
    ("normalized-spend-tamper", lambda p: p["runs"][0]["fetches"][0].update(creditsUsed=0), "differs from captured provider response"),
    ("unknown-spend-without-status", lambda p: p["runs"][0]["fetches"][0]["spend_status"].pop("tokensUsed"), "needs UNKNOWN status"),
    ("authorization-injected", lambda p: p["capture_receipts"][0]["request_headers"].update(Authorization="Bearer probe-not-a-key"), "headers changed"),
    ("paid-route-injected", lambda p: p["free_tier"].update(paid_fallback=True), "not keyless free-only"),
    ("retry-injected", lambda p: p["free_tier"].update(automatic_retries=1), "not keyless free-only"),
    ("request-endpoint-injected", lambda p: p["capture_receipts"][0].update(request_url="https://other.invalid/"), "endpoint/method/headers changed"),
    ("capture-answer-changed", lambda p: p["runs"][0].update(final_answer="Forged answer"), "identity/answer differs"),
    ("capture-citations-changed", lambda p: p["runs"][0].update(citations={"1": "https://other.invalid/"}), "run citations differs"),
    ("judge-row-added-after-capture", lambda p: p["runs"][0].update(judge_decisions=[]), "run judge_decisions differs"),
    ("run-start-changed", lambda p: p["runs"][0].update(started_at="1999-01-01T00:00:00Z"), "start timestamps differ"),
    ("seal-time-changed", lambda p: p["sealed_task_card"].update(sealed_at="2999-01-01T00:00:00Z"), "start timestamps differ"),
    ("receipt-before-preseal", lambda p: p["capture_receipts"][0].update(started_at="1999-01-01T00:00:00Z"), "timestamps"),
    ("response-after-capture", lambda p: p["capture_receipts"][0].update(finished_at="2999-01-01T00:00:00Z"), "timestamps"),
    ("card-goalpost-changed", lambda p: p["task_card"].update(freshness_bound_hours=100000), "seal does not match"),
    ("receipt-omitted", lambda p: p["capture_receipts"].clear(), "one receipt per"),
    ("live-label-downgrade-without-receipt-change", lambda p: (p.update(synthetic=True), p["runs"][0].update(synthetic=True)), "identity/origin mismatch"),
]
for name, mutation, phrase in mutations:
    changed = copy.deepcopy(packet)
    mutation(changed)
    rejects(name, lambda p=changed: validate_live_capture(p), phrase)

for field in ("creditsUsed", "tokensUsed"):
    for label, value in (("negative", -1), ("nan", float("nan")), ("infinity", float("inf")), ("boolean", True), ("string", "0")):
        changed = copy.deepcopy(packet["capture_receipts"][0])
        response = json.loads(base64.b64decode(changed["response_body_base64"]))
        response[field] = value
        response.get("data", {}).get("metadata", {}).pop(field, None)
        body = json.dumps(response).encode()
        changed.update(response_body_base64=base64.b64encode(body).decode(), response_sha256=digest(body), response_bytes=len(body))
        rejects(f"provider-{field}-{label}", lambda r=changed: normalize_live_fetch(r, packet["request_plan"]["fetches"][0]), "must be")

original = Store(ROOT / "data/chain.jsonl")
records = list(original.iter_records())
check("session11-original-chain-verifies", original.verify_chain() == {"ok": True, "records": 10, "first_bad_seq": None, "error": None})
fixture = load_fixture(ROOT / "fixtures/synthetic_firecrawl.json")
old_card = next(r["payload"]["sealed"]["card"] for r in records if r["type"] == "task_card")
old_runs = [r["payload"]["run"] for r in records if r["type"] == "run"]
old_decisions = [r["payload"] for r in records if r["type"] == "queue_decision"]
run_deltas = [{"run_id": new["run_id"], "different_keys": sorted(k for k in set(new) | set(old) if new.get(k) != old.get(k))}
              for new, old in zip(fixture["runs"], old_runs)]
check("recovered-task-card-equals-recorded-card", fixture["task_card"] == old_card)
check("recovered-human-decisions-equal-recorded-decisions", fixture["human_decisions"] == old_decisions)
check("recovered-run-evidence-equals-recorded-evidence", len(fixture["runs"]) == len(old_runs) and all(d["different_keys"] == ["claims_note"] for d in run_deltas), run_deltas)
flags = [f for run in fixture["runs"] for f in grade_run(run, old_card)["flags"]]
precision = compute_precision(decisions_from_chain(original), flags)
check("F3-real-five-decisions-validate-and-precision-80", precision["overall"]["precision"] == .8 and precision["overall"]["confirmed"] == 4 and precision["overall"]["killed"] == 1)
text = render_precision(precision)
check("F6-precision-every-decision-has-seq-and-note", all(f"chain seq {r['seq']}" in text and r["flag_id"] in text and (not r["note"] or r["note"] in text) for r in precision["receipts"]))
for name, decisions in (
    ("orphan", old_decisions + [{"flag_id": "never-emitted", "grader": "completeness", "decision": "confirm"}]),
    ("duplicate", old_decisions + [copy.deepcopy(old_decisions[0])]),
    ("wrong-grader", [{**old_decisions[0], "grader": "unknown"}]),
    ("missing-flag", [{"grader": "completeness", "decision": "confirm"}]),
):
    rejects(f"F3-{name}-decision", lambda d=decisions: compute_precision(d, flags), "invalid precision decision")

with tempfile.TemporaryDirectory(prefix="helper-capture-chain-work-", dir=AUDIT) as scratch:
    scratch = Path(scratch)
    for label, mutation in (
        ("type", lambda r: r.update(type="verdicts")),
        ("timestamp", lambda r: r.update(ts="1999-01-01T00:00:00Z")),
        ("payload", lambda r: r["payload"].update(decision="confirm")),
        ("sequence", lambda r: r.update(seq=11)),
    ):
        changed = copy.deepcopy(records)
        mutation(changed[-1])
        path = scratch / f"helper-{label}.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in changed) + "\n")
        verdict = Store(path).verify_chain()
        check(f"F1-{label}-tamper-rejected", verdict["ok"] is False, verdict)
        before_bad_chain = sha(path)
        calls = [main_call(["precision-demo", "--chain", str(path)]),
                 main_call(["run", "--session1", "--chain", str(path)])]
        check(f"F2-{label}-tamper-no-score-no-append", all(x["exit"] == 1 and not x["stdout"] and "chain verification failed" in x["stderr"] for x in calls) and before_bad_chain == sha(path), calls)
    v1 = copy.deepcopy(records[:1])
    v1[0].pop("hash_version")
    path = scratch / "helper-v1.jsonl"
    path.write_text(json.dumps(v1[0]) + "\n")
    check("F1-old-chain-format-rejected", "old chain format" in Store(path).verify_chain()["error"])
    rejects("F1-old-chain-append-refused", lambda: Store(path).append("run", {"probe": True}), "old chain format")
    raw = json.loads((ROOT / "fixtures/synthetic_firecrawl.json").read_text())
    for label, mutation in (
        ("missing-credits", lambda p: p["runs"][0]["fetches"][0]["response"].pop("creditsUsed")),
        ("missing-tokens", lambda p: p["runs"][0]["fetches"][0].pop("tokensUsed")),
        ("negative-cancellation", lambda p: (p["runs"][0]["fetches"][0]["response"].update(creditsUsed=100), p["runs"][0]["fetches"][1]["response"].update(creditsUsed=-100))),
        ("nonfinite-credits", lambda p: p["runs"][0]["fetches"][0]["response"].update(creditsUsed=float("nan"))),
        ("boolean-tokens", lambda p: p["runs"][0]["fetches"][0].update(tokensUsed=True)),
    ):
        changed = copy.deepcopy(raw)
        mutation(changed)
        path = scratch / f"helper-{label}.json"
        dump(path, changed)
        rejects(f"F4-fixture-{label}-rejected", lambda p=path: load_fixture(p))
    changed = copy.deepcopy(raw)
    changed["human_decisions"].append({"flag_id": "never-emitted", "grader": "completeness", "decision": "confirm"})
    path, chain = scratch / "helper-orphan.json", scratch / "helper-orphan.jsonl"
    dump(path, changed)
    invocation = main_call(["run", "--session1", "--pack", str(path), "--chain", str(chain)])
    check("F3-orphan-CLI-no-score-no-chain-created", invocation["exit"] == 1 and not invocation["stdout"] and not chain.exists(), invocation)
    for label, mutation in (
        ("BLOCKED", lambda p: p.update(capture_status="BLOCKED")),
        ("forged-normalization", lambda p: p["runs"][0]["fetches"][0].update(content_markdown="forged")),
    ):
        changed = copy.deepcopy(packet)
        mutation(changed)
        path, chain = scratch / f"helper-{label}.json", scratch / f"helper-{label}.jsonl"
        dump(path, changed)
        invocation = main_call(["run", "--pack", str(path), "--chain", str(chain)])
        check(f"capture-{label}-CLI-no-score-no-chain-created", invocation["exit"] == 1 and not invocation["stdout"] and not chain.exists(), invocation)

    # Adversarial criteria with a JSON numeric token accepted by Python's
    # parser. Unlike invalid spend, these bounds are admitted and sealed.
    changed = copy.deepcopy(raw)
    changed["human_decisions"] = []
    changed["task_card"]["freshness_bound_hours"] = float("nan")
    for q in changed["task_card"]["questions"]:
        q.pop("freshness_bound_hours", None)
    path = AUDIT / "helper-invalid-bound-repro.json"
    dump(path, changed)
    chain = scratch / "helper-invalid-bound.jsonl"
    invocation = main_call(["run", "--session1", "--pack", str(path), "--chain", str(chain)])
    (AUDIT / "helper-invalid-bound-cli.log").write_text(invocation["stdout"] + "\nSTDERR:\n" + invocation["stderr"])
    repro_pack = load_fixture(path)
    repro_grade = grade_run(repro_pack["runs"][1], repro_pack["task_card"])
    fresh_count = repro_grade["dimensions"]["Freshness"]["flag_count"]
    cost_count = repro_grade["dimensions"]["Cost truth"]["flag_count"]
    finding = {"id": "H-CAP-1", "severity": "MEDIUM", "title": "NaN freshness criterion seals successfully and disables stale-cache check",
               "repro_command": "PYTHONDONTWRITEBYTECODE=1 python3.12 -m scoring.cli run --session1 --pack receipts/audit/helper-invalid-bound-repro.json --chain /a/new/chain/path.jsonl",
               "exit": invocation["exit"], "seal_verifies": verify_seal(seal_task_card(repro_pack["task_card"], "2026-10-27T15:55:00Z")),
               "freshness_flags": fresh_count, "cost_flags": cost_count,
               "total_credits": repro_grade["dimensions"]["Cost truth"]["cost"]["total_credits"],
               "impact": "Malformed data pack admitted as sealed criteria: the known seven-hour stale fixture loses its freshness flag. Not observed in supplied valid live/demo packs; no paid route or real spend was used.",
               "root_cause": "scoring/sealing.py validate_card checks freshness <=0 without math.isfinite; NaN is numeric and NaN <=0 is false. json.loads accepts NaN and age_hours > NaN is false in scoring/graders.py."}
    findings.append(finding)

sealed = seal_task_card(old_card, "2026-10-27T15:55:00Z")
check("F5-complete-seal-envelope-verifies", verify_seal(sealed))
for field in ("sealed_at", "seal_algorithm"):
    changed = copy.deepcopy(sealed)
    changed.pop(field)
    check(f"F5-missing-{field}-rejected", verify_seal(changed) is False)
changed = copy.deepcopy(sealed)
changed["card"]["questions"][0]["question"] += " changed"
check("F5-card-edit-invalidates-seal", verify_seal(changed) is False)
check("F7-progress-task-owner-corrected", "Nov 1, in parallel: the Opus seat's task pack" in (ROOT / "PROGRESS.md").read_text())
after = {str(p.relative_to(ROOT)): sha(p) for p in inputs}
check("source-and-original-evidence-unchanged", before == after)
result = {
    "audit_role": "Independent checker; built none of audited code", "runtime": sys.version,
    "platform": platform.platform(), "network_calls": 0, "new_capture_calls": 0,
    "source_sha256_before": before, "source_sha256_after": after,
    "probe_sha256": sha(Path(__file__)), "live_capture": live_details,
    "reconstructed_run_deltas": run_deltas, "checks": checks,
    "checks_passed": sum(x["pass"] for x in checks), "checks_total": len(checks),
    "findings": findings, "questions_for_Stephen": [],
}
dump(RESULTS, result)
print(json.dumps({"results": str(RESULTS), "checks_passed": result["checks_passed"], "checks_total": result["checks_total"], "findings": findings}, indent=2))
