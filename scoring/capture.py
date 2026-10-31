"""Run capture: the run-record schema and the fixture loader.

A run record is what the harness captures at call time (Session 1:
from fixture files; Session 2 also records keyless free live reads
behind this same schema):

    {run_id, task_card_id, synthetic, agent_label, started_at,
     fetches: [{url, statusCode, cachedAt, cacheState, creditsUsed,
                tokensUsed, content_markdown, relied_on,
                question_ids}],
     final_answer, claims: []}

``claims`` is populated by the Session 2 claim-support grader.
Synthetic fixtures require numeric spend. Live captures retain unavailable
provider spend as None with explicit UNKNOWN status; no missing cost is zero.
``load_task_pack`` loads labeled synthetic data or validates stored live receipts.

Fixture files hold Firecrawl-SHAPED responses (``{success,
creditsUsed, data: {markdown, metadata: {sourceURL, statusCode,
cacheState, cachedAt}}}``) so the loader exercises the same field
paths a live capture will. All fixture content is SYNTHETIC and
invented; the loader refuses a fixture file that is not labeled
synthetic, and every run record it produces carries ``synthetic:
True`` so the label follows the data into every output.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

FETCH_FIELDS = (
    "url",
    "statusCode",
    "cachedAt",
    "cacheState",
    "creditsUsed",
    "tokensUsed",
    "content_markdown",
    "relied_on",
    "question_ids",
)


def _validate_spend(value, field: str, url: str):
    """Return ``value`` if it is a usable spend figure, else raise.

    Spend is evidence: a missing or invalid figure is a rejected
    capture with a named error — never a silent zero (Session 1.1,
    audit fix F4: absent spend used to be replaced with 0, and
    negative entries could cancel real overspend).
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            f"fetch {url}: '{field}' must be a number, got {value!r}"
        )
    if not math.isfinite(value) or value < 0:
        raise ValueError(
            f"fetch {url}: '{field}' must be a non-negative finite "
            f"number, got {value!r}"
        )
    return value


def normalize_fetch(raw: dict) -> dict:
    """Flatten one Firecrawl-shaped fixture fetch into a run-record fetch."""
    if not isinstance(raw, dict) or "response" not in raw:
        raise ValueError("fetch entry needs a 'response' object")
    resp = raw["response"]
    data = resp.get("data") or {}
    meta = data.get("metadata") or {}
    url = meta.get("sourceURL") or raw.get("url")
    if not url:
        raise ValueError("fetch entry has no URL (metadata.sourceURL or url)")
    if "creditsUsed" not in resp:
        raise ValueError(
            f"fetch {url}: missing required spend field 'creditsUsed' "
            "— refusing to substitute zero for missing data"
        )
    if "tokensUsed" not in raw:
        raise ValueError(
            f"fetch {url}: missing required spend field 'tokensUsed' "
            "— refusing to substitute zero for missing data"
        )
    return {
        "url": url,
        "statusCode": meta.get("statusCode"),
        "cachedAt": meta.get("cachedAt"),
        "cacheState": meta.get("cacheState"),
        "creditsUsed": _validate_spend(resp["creditsUsed"], "creditsUsed", url),
        "tokensUsed": _validate_spend(raw["tokensUsed"], "tokensUsed", url),
        "content_markdown": data.get("markdown", ""),
        "relied_on": bool(raw.get("relied_on", False)),
        "question_ids": list(raw.get("question_ids", [])),
    }


def validate_run(run: dict, *, allow_unknown_spend: bool = False) -> None:
    """Raise ValueError unless ``run`` is a well-formed run record."""
    if not isinstance(run, dict):
        raise ValueError("run record must be a JSON object")
    for field in ("run_id", "task_card_id", "agent_label", "started_at"):
        if not run.get(field):
            raise ValueError(f"run record needs '{field}'")
    fetches = run.get("fetches")
    if not isinstance(fetches, list) or not fetches:
        raise ValueError("run record needs a non-empty 'fetches' list")
    for fetch in fetches:
        missing = [f for f in FETCH_FIELDS if f not in fetch]
        if missing:
            raise ValueError(
                f"fetch {fetch.get('url', '?')} missing fields: {missing}"
            )
        for field in ("creditsUsed", "tokensUsed"):
            if fetch[field] is None and allow_unknown_spend:
                if (run.get("synthetic") is not False
                        and run.get("capture_origin") != "firecrawl-keyless-v1"):
                    raise ValueError("unknown spend is allowed only for explicit captures")
                if fetch.get("spend_status", {}).get(field) != "UNKNOWN":
                    raise ValueError(
                        f"fetch {fetch.get('url', '?')}: {field} None needs UNKNOWN status"
                    )
                continue
            _validate_spend(fetch[field], field,
                            fetch.get("url", "?"))
    if not isinstance(run.get("final_answer"), str):
        raise ValueError("run record needs a 'final_answer' string")
    if not isinstance(run.get("claims"), list):
        raise ValueError("run record needs a 'claims' list (may be empty)")


def load_fixture(path) -> dict:
    """Load a fixture file -> {task_card, runs, human_decisions}.

    Refuses any file not labeled synthetic: fixture data must never be
    mistakable for real Firecrawl output.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("synthetic") is not True:
        raise ValueError(
            "fixture file is not labeled synthetic — refusing to load"
        )
    card = raw["task_card"]
    runs = []
    for raw_run in raw["runs"]:
        run = {
            **copy.deepcopy(raw_run),
            "run_id": raw_run["run_id"],
            "task_card_id": card["id"],
            "synthetic": True,
            "agent_label": raw_run.get("agent_label", "fixture-agent"),
            "started_at": raw_run["started_at"],
            "fetches": [normalize_fetch(f) for f in raw_run["fetches"]],
            "final_answer": raw_run.get("final_answer", ""),
            "claims": copy.deepcopy(raw_run.get("claims", [])),
            "claims_note": "Session 2 claim-support extraction runs before grading.",
        }
        validate_run(run)
        runs.append(run)
    return {
        "task_card": card,
        "runs": runs,
        "human_decisions": raw.get("human_decisions", []),
    }


def load_task_pack(path) -> dict:
    """Load a data-only synthetic fixture or receipted live capture.

    Live receipts are checked before any score can be produced. This validates
    receipt integrity and the normalized run's equality to the recorded body;
    it does not attest that an untrusted file was fetched from the Internet.
    The chain seals the evidence when the caller records it.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("task pack must be a JSON object")
    if raw.get("capture_kind") is None and raw.get("synthetic") is True:
        return load_fixture(path)
    from .live import validate_live_capture
    validate_live_capture(raw)
    return {
        "task_card": raw["task_card"],
        "sealed_task_card": raw["sealed_task_card"],
        "runs": copy.deepcopy(raw["runs"]),
        "human_decisions": copy.deepcopy(raw.get("human_decisions", [])),
        "capture_status": raw["capture_status"],
        "capture_receipts": copy.deepcopy(raw["capture_receipts"]),
    }
