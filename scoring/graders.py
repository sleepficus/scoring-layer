"""The four deterministic graders (Session 1).

No judge seat anywhere in this module: every flag is arithmetic or
string matching against the sealed task card, and every flag carries
its evidence receipt — the fetched document's fields, the sealed
criterion, the exact numbers. A flag is:

    {flag_id, grader, dimension, criterion, subject, evidence}

``flag_id`` is deterministic within a run:
``<run_id>:<grader>:<n>`` in firing order.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .sealing import freshness_bound_for

# Content-shape markers of a block / challenge / error page served AS
# a document. Deliberately conservative common phrases.
BLOCK_MARKERS = (
    "403 forbidden",
    "access denied",
    "are you a robot",
    "checking your browser",
    "verify you are human",
    "captcha",
    "just a moment...",
    "attention required",
    "request blocked",
)


def parse_ts(value: str) -> datetime:
    """Parse an ISO-8601 timestamp ('Z' suffix accepted) to aware UTC."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _flagger(run: dict):
    counter = {"n": 0}

    def make(grader: str, dimension: str, criterion: str, subject: str,
             evidence: dict) -> dict:
        counter["n"] += 1
        return {
            "flag_id": f"{run['run_id']}:{grader}:{counter['n']}",
            "grader": grader,
            "dimension": dimension,
            "criterion": criterion,
            "subject": subject,
            "evidence": evidence,
        }

    return make


def _content_for_question(run: dict, question_id: str) -> str:
    """Markdown the agent consumed for one question: fetches assigned
    to it, or all fetches when none are assigned."""
    assigned = [f for f in run["fetches"] if question_id in f["question_ids"]]
    pool = assigned if assigned else run["fetches"]
    return "\n".join(f["content_markdown"] for f in pool)


def grade_fetch_truth(run: dict) -> list[dict]:
    """Flag relied-on documents that are not real 200 documents.

    Two deterministic tests per relied-on fetch: (a) the response
    statusCode is not 200 — the Firecrawl billing-docs failure, an
    error page delivered (and charged) as a document; (b) the content
    shape matches a block/challenge page even under a 200.
    """
    make = _flagger(run)
    flags = []
    for fetch in run["fetches"]:
        if not fetch["relied_on"]:
            continue
        reasons = []
        if fetch["statusCode"] != 200:
            reasons.append(f"statusCode is {fetch['statusCode']}, not 200")
        content = fetch["content_markdown"].lower()
        hits = [m for m in BLOCK_MARKERS if m in content]
        if hits:
            reasons.append(f"content matches block/challenge markers: {hits}")
        if reasons:
            flags.append(make(
                "fetch-truth", "Fetch truth",
                "A relied-on document must be a real 200 document, not an "
                "error, block, or challenge page delivered as a document.",
                fetch["url"],
                {
                    "statusCode": fetch["statusCode"],
                    "cacheState": fetch["cacheState"],
                    "creditsUsed": fetch["creditsUsed"],
                    "reasons": reasons,
                    "content_excerpt": fetch["content_markdown"][:200],
                },
            ))
    return flags


def grade_freshness(run: dict, card: dict) -> list[dict]:
    """Flag relied-on fetches whose cachedAt is older than the sealed
    freshness bound governing their question(s)."""
    make = _flagger(run)
    flags = []
    started = parse_ts(run["started_at"])
    for fetch in run["fetches"]:
        if not fetch["relied_on"]:
            continue
        question_ids = fetch["question_ids"] or [q["id"] for q in card["questions"]]
        bound = min(freshness_bound_for(card, qid) for qid in question_ids)
        if fetch["cachedAt"] is None:
            flags.append(make(
                "freshness", "Freshness",
                "A relied-on document must carry a cachedAt inside the "
                "sealed freshness bound; no cachedAt means freshness "
                "cannot be verified.",
                fetch["url"],
                {"cachedAt": None, "bound_hours": bound,
                 "question_ids": question_ids},
            ))
            continue
        age_hours = (started - parse_ts(fetch["cachedAt"])).total_seconds() / 3600.0
        if age_hours > bound:
            flags.append(make(
                "freshness", "Freshness",
                "cachedAt must be inside the sealed freshness bound.",
                fetch["url"],
                {
                    "cachedAt": fetch["cachedAt"],
                    "run_started_at": run["started_at"],
                    "age_hours": round(age_hours, 3),
                    "bound_hours": bound,
                    "cacheState": fetch["cacheState"],
                    "question_ids": question_ids,
                },
            ))
    return flags


def completeness_detail(run: dict, card: dict) -> dict:
    """Per-question required-element presence — the receipts under
    both the completeness flags and the cost grader's denominator."""
    detail = {}
    for q in card["questions"]:
        content = _content_for_question(run, q["id"]).lower()
        present = [e for e in q["required_elements"] if e.lower() in content]
        missing = [e for e in q["required_elements"] if e.lower() not in content]
        detail[q["id"]] = {"present": present, "missing": missing}
    return detail


def grade_completeness(run: dict, card: dict) -> list[dict]:
    """Flag required elements (sealed in the task card) missing from
    the content the agent actually consumed — the missing_markdown
    failure, scored explicitly."""
    make = _flagger(run)
    flags = []
    detail = completeness_detail(run, card)
    for q in card["questions"]:
        for element in detail[q["id"]]["missing"]:
            flags.append(make(
                "completeness", "Completeness",
                "Every required element sealed in the task card must "
                "appear in the content the agent consumed.",
                f"{q['id']}: {element}",
                {
                    "question_id": q["id"],
                    "question": q["question"],
                    "missing_element": element,
                    "present_elements": detail[q["id"]]["present"],
                    "fetched_urls": [
                        f["url"] for f in run["fetches"]
                        if q["id"] in f["question_ids"]
                    ],
                },
            ))
    return flags


def cost_detail(run: dict, card: dict, detail: dict | None = None) -> dict:
    """The cost arithmetic, receipted: totals from the captured
    fetches; verified facts = required elements found present."""
    if detail is None:
        detail = completeness_detail(run, card)
    # Live providers do not always report metering. Unknown evidence stays
    # unknown for that unit; a zero would falsely claim a measured free run.
    total_credits = (sum(f["creditsUsed"] for f in run["fetches"])
                     if all(f["creditsUsed"] is not None for f in run["fetches"])
                     else None)
    total_tokens = (sum(f["tokensUsed"] for f in run["fetches"])
                    if all(f["tokensUsed"] is not None for f in run["fetches"])
                    else None)
    verified = sum(len(v["present"]) for v in detail.values())
    required = sum(len(v["present"]) + len(v["missing"]) for v in detail.values())
    return {
        "total_credits": total_credits,
        "total_tokens": total_tokens,
        "verified_facts": verified,
        "required_facts": required,
        "credits_per_verified_fact": (
            round(total_credits / verified, 4)
            if verified and total_credits is not None else None
        ),
        "tokens_per_verified_fact": (
            round(total_tokens / verified, 4)
            if verified and total_tokens is not None else None
        ),
        "cost_bound": card["cost_bound"],
        "per_fetch": [
            {"url": f["url"], "creditsUsed": f["creditsUsed"],
             "tokensUsed": f["tokensUsed"]}
            for f in run["fetches"]
        ],
    }


def grade_cost(run: dict, card: dict, detail: dict | None = None) -> list[dict]:
    """Flag a run whose captured spend breaks the sealed cost bound."""
    make = _flagger(run)
    cost = cost_detail(run, card, detail)
    flags = []
    bound = card["cost_bound"]
    unknown = [unit for unit in ("credits", "tokens")
               if cost[f"total_{unit}"] is None]
    if unknown:
        flags.append(make(
            "cost-truth", "Cost truth",
            "Captured spend must be known to verify the sealed cost bound; "
            "unknown metering is UNVERIFIABLE, never zero or a pass.",
            run["run_id"], {**cost, "status": "UNVERIFIABLE", "unknown_units": unknown},
        ))
    if (cost["total_credits"] is not None
        and cost["total_credits"] > bound["max_credits"]) or (
        cost["total_tokens"] is not None
        and cost["total_tokens"] > bound["max_tokens"]
    ):
        flags.append(make(
            "cost-truth", "Cost truth",
            "Captured run spend must stay inside the sealed cost bound.",
            run["run_id"],
            cost,
        ))
    return flags


def grade_run(run: dict, card: dict) -> dict:
    """Run all four deterministic graders over one run record.

    Returns per-dimension receipts: flag counts with the flags
    themselves listed under each number (Scorer doctrine — every
    number drills to its receipts), plus the completeness and cost
    detail the numbers came from.
    """
    detail = completeness_detail(run, card)
    cost = cost_detail(run, card, detail)
    dimensions = {}

    fetch_flags = grade_fetch_truth(run)
    dimensions["Fetch truth"] = {
        "grader": "fetch-truth",
        "relied_on_fetches": sum(1 for f in run["fetches"] if f["relied_on"]),
        "total_fetches": len(run["fetches"]),
        "flag_count": len(fetch_flags),
        "flags": fetch_flags,
    }

    fresh_flags = grade_freshness(run, card)
    dimensions["Freshness"] = {
        "grader": "freshness",
        "bound_hours": card["freshness_bound_hours"],
        "flag_count": len(fresh_flags),
        "flags": fresh_flags,
    }

    comp_flags = grade_completeness(run, card)
    dimensions["Completeness"] = {
        "grader": "completeness",
        "required_elements": cost["required_facts"],
        "present_elements": cost["verified_facts"],
        "missing_elements": cost["required_facts"] - cost["verified_facts"],
        "detail": detail,
        "flag_count": len(comp_flags),
        "flags": comp_flags,
    }

    cost_flags = grade_cost(run, card, detail)
    dimensions["Cost truth"] = {
        "grader": "cost-truth",
        "cost": cost,
        "flag_count": len(cost_flags),
        "flags": cost_flags,
    }

    all_flags = fetch_flags + fresh_flags + comp_flags + cost_flags
    return {
        "run_id": run["run_id"],
        "task_card_id": card["id"],
        "synthetic": bool(run.get("synthetic")),
        "dimensions": dimensions,
        "flags": all_flags,
        "flag_count": len(all_flags),
    }


def grade_session2_run(run: dict, card: dict, judge_decisions=None) -> dict:
    """Grade the Session 2 ledger while preserving the Session 1 API.

    ``grade_run`` remains the four-grader historical replay. This wrapper
    re-extracts every candidate claim before the caller stores the run,
    adds citation-bound support receipts, and reports deterministic and
    judge counts/cost denominators separately. A JUDGE result never
    upgrades the deterministic verdict or its verified-claim denominator.
    """
    from .capture import validate_run
    from .claims import grade_claim_support
    from .sealing import seal_card

    validate_run(run, allow_unknown_spend=(run.get("synthetic") is False or
                 run.get("capture_origin") == "firecrawl-keyless-v1"))
    if run["task_card_id"] != card["id"]:
        raise ValueError("run task_card_id does not match the task card")
    result = grade_run(run, card)
    support = grade_claim_support(run, judge_decisions=judge_decisions)
    result["dimensions"]["Claim support"] = support
    result["flags"] += support["flags"]
    result["flag_count"] = len(result["flags"])
    result["session"] = 2
    result["task_card_seal"] = seal_card(card)
    run["task_card_seal"] = result["task_card_seal"]
    cost = result["dimensions"]["Cost truth"]["cost"]
    result["claim_cost"] = {
        "scope": "Captured fetch spend only; answer-generation tokens and any separate judge-seat cost are UNKNOWN.",
        "total_credits": cost["total_credits"],
        "total_tokens": cost["total_tokens"],
        "deterministic": {},
        "judge": {},
    }
    for method in ("deterministic", "judge"):
        count = support[method]["SUPPORTED"]
        result["claim_cost"][method] = {
            "supported_claims": count,
            "credits_per_supported_claim": (
                round(cost["total_credits"] / count, 4)
                if count and cost["total_credits"] is not None else None),
            "tokens_per_supported_claim": (
                round(cost["total_tokens"] / count, 4)
                if count and cost["total_tokens"] is not None else None),
        }
    return result
