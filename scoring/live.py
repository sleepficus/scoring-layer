"""Receipted Firecrawl reads through the documented keyless free route.

This module never reads API keys, sends Authorization, retries a request,
follows an API redirect, or upgrades a plan. The only endpoint is the public
Cloud /v2/scrape endpoint, and the only requested format is markdown.
Official basis checked 2026-10-28: https://docs.firecrawl.dev/rate-limits
and https://docs.firecrawl.dev/capabilities . Keyless limits stop the run.

The provider may omit credits, tokens and cache metadata. They stay UNKNOWN;
an observed document is still preserved and usable for claim-support grading.
The caller supplies the final answer; this is a read-capture harness, not an
autonomous answer-writing agent. Agent generation token usage is UNKNOWN.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPHandler, HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request,
    build_opener,
)

from .capture import _validate_spend, validate_run
from .sealing import canonical, seal_task_card, validate_card, verify_seal

ENDPOINT = "https://api.firecrawl.dev/v2/scrape"
CAPTURE_KIND = "firecrawl-keyless-v1"
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
DOC_SOURCES = [
    "https://docs.firecrawl.dev/rate-limits#keyless-no-api-key",
    "https://docs.firecrawl.dev/capabilities",
    "https://docs.firecrawl.dev/api-reference/endpoint/scrape",
]


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(body: bytes):
    return hashlib.sha256(body).hexdigest()


def _json_hash(obj):
    return _sha(canonical(obj).encode("utf-8"))


def _timestamp(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"live {name} needs an aware ISO-8601 timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"live {name} needs an aware ISO-8601 timestamp") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"live {name} needs an aware ISO-8601 timestamp")
    return result


def _valid_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    return (parsed.scheme in ("http", "https") and bool(parsed.hostname)
            and parsed.username is None and parsed.password is None)


def _validate_plan(plan):
    if not isinstance(plan, dict):
        raise ValueError("live task pack must be a JSON object")
    allowed = {"task_card", "run_id", "agent_label", "final_answer", "fetches",
               "citations", "judge_decisions", "notes"}
    if set(plan) - allowed:
        raise ValueError(f"unsupported live task-pack fields: {sorted(set(plan) - allowed)}")
    validate_card(plan.get("task_card"))
    for name in ("run_id", "agent_label", "final_answer"):
        if not isinstance(plan.get(name), str) or not plan[name].strip():
            raise ValueError(f"live task pack needs non-empty {name}")
    fetches = plan.get("fetches")
    if not isinstance(fetches, list) or not fetches:
        raise ValueError("live task pack needs non-empty fetches")
    question_ids = {q["id"] for q in plan["task_card"]["questions"]}
    urls = set()
    for entry in fetches:
        if not isinstance(entry, dict) or set(entry) - {"url", "question_ids", "relied_on"}:
            raise ValueError("each live fetch accepts only url, question_ids, relied_on")
        if not _valid_url(entry.get("url")):
            raise ValueError("live fetch needs a public HTTP(S) URL without credentials")
        if entry["url"] in urls:
            raise ValueError("duplicate live fetch URLs are ambiguous; use one capture per URL")
        urls.add(entry["url"])
        if not isinstance(entry.get("relied_on"), bool):
            raise ValueError("live fetch relied_on must be boolean")
        qids = entry.get("question_ids")
        if not isinstance(qids, list) or any(q not in question_ids for q in qids):
            raise ValueError("live fetch question_ids must reference the sealed task card")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _http_transport(request, timeout):
    """One unauthenticated POST; no ambient proxies, cookies or redirects."""
    req = Request(request["url"], data=request["body"],
                  headers=request["headers"], method="POST")
    opener = build_opener(ProxyHandler({}), HTTPHandler(), HTTPSHandler(), _NoRedirect())
    try:
        response = opener.open(req, timeout=timeout)
    except HTTPError as exc:
        response = exc  # HTTP errors carry the original response body too.
    with response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ValueError("Firecrawl response exceeded 10 MiB; refusing to truncate evidence")
        return {"status_code": response.code,
                "headers": dict(response.headers.items()), "body": body}


def _request_for(entry):
    body = canonical({"url": entry["url"], "formats": ["markdown"],
                      "onlyMainContent": True}).encode("utf-8")
    return {"method": "POST", "url": ENDPOINT,
            "headers": {"Content-Type": "application/json", "Accept": "application/json",
                        "User-Agent": "ScoringLayer-Session2/0.2 keyless-free-only"},
            "body": body}


def _receipt(request, response, started, finished, entry, index, transport_kind):
    body = response["body"]
    if not isinstance(body, bytes):
        raise ValueError("transport body must be exact bytes")
    headers = {str(k).lower(): str(v) for k, v in response.get("headers", {}).items()
               if str(k).lower() in {"content-type", "date", "retry-after", "x-request-id",
                                    "x-ratelimit-limit", "x-ratelimit-remaining",
                                    "x-ratelimit-reset"}}
    return {"receipt_index": index, "transport": transport_kind, "outcome": "HTTP_RESPONSE",
            "started_at": started, "finished_at": finished,
            "requested_url": entry["url"], "request_url": request["url"],
            "request_method": request["method"], "request_headers": request["headers"],
            "request_body": request["body"].decode("utf-8"),
            "request_sha256": _sha(request["body"]),
            "http_status": response["status_code"], "response_headers": headers,
            "response_body_base64": base64.b64encode(body).decode("ascii"),
            "response_sha256": _sha(body), "response_bytes": len(body)}


def _attempt_receipt(request, started, entry, index, transport_kind):
    return {"receipt_index": index, "transport": transport_kind, "outcome": "REQUESTED",
            "started_at": started, "finished_at": None,
            "requested_url": entry["url"], "request_url": request["url"],
            "request_method": request["method"], "request_headers": request["headers"],
            "request_body": request["body"].decode("utf-8"),
            "request_sha256": _sha(request["body"]), "http_status": None,
            "response_headers": {}, "response_body_base64": None,
            "response_sha256": None, "response_bytes": None}


def _body_from_receipt(receipt):
    try:
        body = base64.b64decode(receipt["response_body_base64"], validate=True)
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError("live response receipt has invalid base64") from exc
    if _sha(body) != receipt.get("response_sha256") or len(body) != receipt.get("response_bytes"):
        raise ValueError("live response receipt hash/size mismatch")
    try:
        result = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Firecrawl response was not JSON; raw response preserved") from exc
    if not isinstance(result, dict):
        raise ValueError("Firecrawl response must be a JSON object")
    return result


def normalize_live_fetch(receipt, entry):
    """Normalize the exact recorded provider body without inventing metadata."""
    resp = _body_from_receipt(receipt)
    if receipt["http_status"] != 200 or resp.get("success") is not True:
        raise ValueError("Firecrawl did not return a successful document; raw response preserved")
    data = resp.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("markdown"), str):
        raise ValueError("Firecrawl omitted markdown; raw response preserved")
    meta = data.get("metadata") or {}
    if not isinstance(meta, dict):
        raise ValueError("Firecrawl metadata must be an object")
    url = meta.get("sourceURL") or meta.get("url") or entry["url"]
    if not _valid_url(url):
        raise ValueError("Firecrawl document source URL is invalid")
    # Both top-level legacy and current metadata placement are observed APIs;
    # prefer neither when they disagree. An unknown figure stays unknown.
    spend = {}
    spend_sources = {}
    for name in ("creditsUsed", "tokensUsed"):
        figures = [(f"response.{name}", resp[name])] if name in resp else []
        if name in meta:
            figures.append((f"response.data.metadata.{name}", meta[name]))
        if figures:
            for _, value in figures:
                _validate_spend(value, name, url)
            if len({value for _, value in figures}) != 1:
                raise ValueError(f"conflicting provider {name}; raw response preserved")
            spend[name] = figures[0][1]
            spend_sources[name] = [path for path, _ in figures]
        else:
            spend[name] = None
            spend_sources[name] = []
    return {"url": url, "requested_url": entry["url"],
            "statusCode": meta.get("statusCode"), "cachedAt": meta.get("cachedAt"),
            "cacheState": meta.get("cacheState"), **spend,
            "content_markdown": data["markdown"], "relied_on": entry["relied_on"],
            "question_ids": copy.deepcopy(entry["question_ids"]),
            "spend_status": {k: "UNKNOWN" if v is None else "PROVIDER_REPORTED"
                             for k, v in spend.items()},
            "spend_sources": spend_sources,
            "tokens_scope": "provider-reported scrape tokens only; agent generation tokens UNKNOWN",
            "receipt_index": receipt["receipt_index"],
            "content_sha256": _sha(data["markdown"].encode("utf-8"))}


def _save(path, packet, *, create=False):
    text = json.dumps(packet, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if create:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
    else:
        # Each response is durable before the next request starts.
        temp = path.with_name(path.name + ".writing")
        with temp.open("x", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)


def capture_live_task_pack(pack_path, output_path, *, transport=None, timeout=45,
                           api_key=None):
    """Capture data-only plan to a write-once output, returning its packet.

    Injected transports are labeled SYNTHETIC mock capture, never live proof.
    Limits/errors are returned as BLOCKED/INCOMPLETE packets with raw receipts;
    no partial packet can be loaded for scoring. Existing output is refused
    before any network call, preventing accidental replay to the same path.
    """
    if api_key is not None:
        raise ValueError("Session 2 supports keyless free capture only; API keys are refused")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 60:
        raise ValueError("capture timeout must be a finite number in (0, 60] seconds")
    plan = json.loads(Path(pack_path).read_text(encoding="utf-8"))
    _validate_plan(plan)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    synthetic = transport is not None
    transport_kind = "SYNTHETIC_TEST_TRANSPORT" if synthetic else "urllib-http"
    started = _now()
    packet = {"capture_kind": CAPTURE_KIND, "synthetic": synthetic,
              "capture_status": "INCOMPLETE", "capture_started_at": started,
              "task_card": copy.deepcopy(plan["task_card"]),
              "sealed_task_card": seal_task_card(plan["task_card"], started),
              "request_plan": plan, "request_plan_sha256": _json_hash(plan),
              "capture_receipts": [], "capture_errors": [], "runs": [],
              "human_decisions": [],
              "free_tier": {"route": "KEYLESS", "authorization_sent": False,
                            "paid_fallback": False, "automatic_retries": 0,
                            "basis_checked_at": "2026-10-28", "source_urls": DOC_SOURCES},
              "answer_origin": "caller-supplied; capture performs no agent generation"}
    _save(path, packet, create=True)
    do_request = transport or _http_transport
    fetches = []
    for index, entry in enumerate(plan["fetches"]):
        request = _request_for(entry)
        call_started = _now()
        # Record the attempted request before sending it. A network timeout
        # leaves an honest attempted-call receipt with unknown response/spend.
        packet["capture_receipts"].append(
            _attempt_receipt(request, call_started, entry, index, transport_kind))
        _save(path, packet)
        try:
            response = do_request(request, timeout)
            receipt = _receipt(request, response, call_started, _now(), entry,
                               index, transport_kind)
            packet["capture_receipts"][index] = receipt
            _save(path, packet)
            if response["status_code"] in (402, 429):
                packet["capture_status"] = "BLOCKED"
                raise ValueError(f"free-tier limit HTTP {response['status_code']}; wait for reset, no paid fallback")
            fetches.append(normalize_live_fetch(receipt, entry))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            if packet["capture_receipts"][index]["outcome"] == "REQUESTED":
                packet["capture_receipts"][index]["outcome"] = "TRANSPORT_ERROR"
                packet["capture_receipts"][index]["finished_at"] = _now()
            packet["capture_errors"].append({"fetch_index": index, "url": entry["url"],
                                             "error": str(exc), "recorded_at": _now()})
            break
    else:
        run = {"run_id": plan["run_id"], "task_card_id": plan["task_card"]["id"],
               "synthetic": synthetic, "capture_origin": CAPTURE_KIND,
               "agent_label": plan["agent_label"], "started_at": started,
               "fetches": fetches, "final_answer": plan["final_answer"], "claims": [],
               "claims_note": "Session 2 extracts claims before grading.",
               "answer_origin": "caller-supplied; capture performs no agent generation",
               "agent_generation_tokens": None,
               "agent_generation_tokens_status": "UNKNOWN"}
        for key in ("citations", "judge_decisions"):
            if key in plan:
                run[key] = copy.deepcopy(plan[key])
        validate_run(run, allow_unknown_spend=True)
        packet["runs"] = [run]
        packet["capture_status"] = "COMPLETE"
    packet["capture_finished_at"] = _now()
    _save(path, packet)
    return packet


def validate_live_capture(packet):
    """Check stored capture/normalization integrity; refuse incomplete reads."""
    if not isinstance(packet, dict) or packet.get("capture_kind") != CAPTURE_KIND:
        raise ValueError("unrecognized live capture format")
    if packet.get("capture_status") != "COMPLETE" or packet.get("capture_errors"):
        raise ValueError(f"capture is {packet.get('capture_status', 'UNKNOWN')}; cannot score partial/blocked evidence")
    if not isinstance(packet.get("synthetic"), bool):
        raise ValueError("capture must declare synthetic boolean")
    plan = packet.get("request_plan")
    _validate_plan(plan)
    if _json_hash(plan) != packet.get("request_plan_sha256"):
        raise ValueError("live request plan hash mismatch")
    sealed = packet.get("sealed_task_card")
    if not verify_seal(sealed) or sealed["card"] != packet.get("task_card") or plan["task_card"] != packet["task_card"]:
        raise ValueError("live task card seal does not match captured criteria")
    expected_free = {"route": "KEYLESS", "authorization_sent": False,
                     "paid_fallback": False, "automatic_retries": 0}
    free = packet.get("free_tier", {})
    if any(free.get(k) != v for k, v in expected_free.items()):
        raise ValueError("capture is not keyless free-only")
    runs, receipts = packet.get("runs"), packet.get("capture_receipts")
    if not isinstance(runs, list) or len(runs) != 1 or not isinstance(receipts, list) or len(receipts) != len(plan["fetches"]):
        raise ValueError("live capture needs one complete run and one receipt per requested read")
    run = runs[0]
    validate_run(run, allow_unknown_spend=True)
    if run.get("synthetic") != packet["synthetic"] or run.get("capture_origin") != CAPTURE_KIND:
        raise ValueError("run origin label differs from capture")
    if any(run.get(k) != plan[k] for k in ("run_id", "agent_label", "final_answer")) or run["task_card_id"] != plan["task_card"]["id"]:
        raise ValueError("run identity/answer differs from captured request plan")
    for key in ("citations", "judge_decisions"):
        if ((key in run) != (key in plan)
                or (key in plan and canonical(run[key]) != canonical(plan[key]))):
            raise ValueError(f"run {key} differs from captured request plan")
    started_at = packet.get("capture_started_at")
    if run.get("started_at") != started_at or sealed.get("sealed_at") != started_at:
        raise ValueError("run/card start timestamps differ from original capture_started_at")
    started = _timestamp(started_at, "capture_started_at")
    finished = _timestamp(packet.get("capture_finished_at"), "capture_finished_at")
    if finished < started:
        raise ValueError("capture timestamps are out of order")
    if len(run["fetches"]) != len(receipts):
        raise ValueError("live normalized fetch/receipt count mismatch")
    expected_transport = "SYNTHETIC_TEST_TRANSPORT" if packet["synthetic"] else "urllib-http"
    previous_finished = started
    for index, (entry, receipt, fetch) in enumerate(zip(plan["fetches"], receipts, run["fetches"])):
        call_started = _timestamp(receipt.get("started_at"), "receipt.started_at")
        call_finished = _timestamp(receipt.get("finished_at"), "receipt.finished_at")
        if not previous_finished <= call_started <= call_finished <= finished:
            raise ValueError("live receipt timestamps are out of capture order")
        previous_finished = call_finished
        expected_request = _request_for(entry)
        if receipt.get("request_url") != ENDPOINT or receipt.get("request_method") != "POST" or receipt.get("request_headers") != expected_request["headers"]:
            raise ValueError("live request endpoint/method/headers changed")
        if receipt.get("request_body") != expected_request["body"].decode("utf-8") or receipt.get("request_sha256") != _sha(expected_request["body"]):
            raise ValueError("live request body hash mismatch")
        if receipt.get("receipt_index") != index or receipt.get("transport") != expected_transport or receipt.get("requested_url") != entry["url"] or receipt.get("outcome") != "HTTP_RESPONSE":
            raise ValueError("live receipt identity/origin mismatch")
        if normalize_live_fetch(receipt, entry) != fetch:
            raise ValueError("normalized live fetch differs from captured provider response")
