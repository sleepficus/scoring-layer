"""Grader-precision scorecard math.

The grading system is itself graded: every flag a grader fires can be
confirmed or killed by a human reviewer in the queue. Precision, per
grader and overall, is::

    precision = confirmed / (confirmed + killed)

over decided flags only. Undecided flags are reported as pending and
never counted for or against the grader. With no decisions, precision
is None — printed as UNVERIFIED, never as 100% (a grader nobody has
checked has not earned a number).

A decision is ``{flag_id, grader, decision}`` with decision in
``{"confirm", "kill"}`` — the same shape the queue writes as
``queue_decision`` chain records; :func:`decisions_from_chain`
extracts them.

**Decision validation (Session 1.1, audit fix F3).** A decision only
counts when it is *about a real flag*: ``flag_id`` is required; when
the emitted flag list is supplied, the flag_id must reference an
actually-emitted flag and the decision's grader must be that flag's
grader; and each flag may be decided at most once. Any violation
raises ValueError naming every problem found — invalid decisions are
reported as errors and never reach the tally, so a stray, duplicate,
or misattributed decision cannot move the score.

The result carries ``receipts``: the validated decisions in input
order, each with its flag_id, grader, decision, note (when present),
and chain ``seq`` (when the decision came from the chain) — the
per-decision evidence under the precision number (audit fix F6).
"""

from __future__ import annotations

DECISIONS = ("confirm", "kill")


def _validate_decisions(decisions: list[dict],
                        flags: list[dict] | None) -> list[str]:
    """Return every validation problem found in ``decisions``."""
    errors = []
    flag_by_id = None
    if flags is not None:
        flag_by_id = {f["flag_id"]: f for f in flags}
    seen_ids = set()
    for idx, d in enumerate(decisions):
        label = f"decision #{idx + 1}"
        if d.get("decision") not in DECISIONS:
            errors.append(
                f"{label}: unknown decision: {d.get('decision')!r}"
            )
        if not d.get("grader"):
            errors.append(f"{label}: each decision needs a 'grader'")
        flag_id = d.get("flag_id")
        if not flag_id:
            errors.append(f"{label}: each decision needs a 'flag_id'")
            continue
        if flag_id in seen_ids:
            errors.append(
                f"{label}: duplicate decision for flag {flag_id!r} — "
                "each flag may be decided at most once"
            )
            continue
        seen_ids.add(flag_id)
        if flag_by_id is not None:
            flag = flag_by_id.get(flag_id)
            if flag is None:
                errors.append(
                    f"{label}: references flag {flag_id!r}, which no "
                    "grader emitted"
                )
            elif d.get("grader") != flag["grader"]:
                errors.append(
                    f"{label}: grader {d.get('grader')!r} does not "
                    f"match flag {flag_id!r}'s grader "
                    f"{flag['grader']!r}"
                )
    return errors


def _tally(decisions: list[dict]) -> dict:
    confirmed = sum(1 for d in decisions if d["decision"] == "confirm")
    killed = sum(1 for d in decisions if d["decision"] == "kill")
    decided = confirmed + killed
    return {
        "confirmed": confirmed,
        "killed": killed,
        "decided": decided,
        "precision": (round(confirmed / decided, 4) if decided else None),
    }


def compute_precision(decisions: list[dict],
                      flags: list[dict] | None = None) -> dict:
    """Precision per grader + overall from confirm/kill decisions.

    ``flags`` (optional) is the full flag list: it lets pending
    (undecided) flags be counted per grader, and — when supplied —
    decisions are validated against it (see module docstring).
    Raises ValueError naming every invalid decision; invalid
    decisions are never counted.
    """
    errors = _validate_decisions(decisions, flags)
    if errors:
        raise ValueError(
            "invalid precision decision(s): " + "; ".join(errors)
        )
    graders = sorted({d["grader"] for d in decisions} |
                     {f["grader"] for f in (flags or [])})
    decided_ids = {d["flag_id"] for d in decisions}
    per_grader = {}
    for grader in graders:
        entry = _tally([d for d in decisions if d["grader"] == grader])
        entry["pending"] = sum(
            1 for f in (flags or [])
            if f["grader"] == grader and f["flag_id"] not in decided_ids
        )
        per_grader[grader] = entry
    overall = _tally(decisions)
    overall["pending"] = sum(
        1 for f in (flags or []) if f["flag_id"] not in decided_ids
    )
    receipts = [
        {
            "flag_id": d["flag_id"],
            "grader": d["grader"],
            "decision": d["decision"],
            "seq": d.get("seq"),
            "note": d.get("note"),
        }
        for d in decisions
    ]
    return {"per_grader": per_grader, "overall": overall,
            "receipts": receipts}


def decisions_from_chain(store) -> list[dict]:
    """Extract confirm/kill decisions from a chain Store's
    ``queue_decision`` records, in chain order. Each decision carries
    the ``seq`` of the record it came from (its receipt pointer) and
    the record's ``note`` when one was written."""
    decisions = []
    for record in store.iter_records(type="queue_decision"):
        payload = record["payload"]
        decisions.append({
            "flag_id": payload.get("flag_id"),
            "grader": payload.get("grader"),
            "decision": payload.get("decision"),
            "seq": record.get("seq"),
            "note": payload.get("note"),
        })
    return decisions
