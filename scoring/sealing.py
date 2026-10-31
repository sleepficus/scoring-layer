"""Task-card sealing.

A task card fixes the criteria BEFORE a run: the questions, the
required elements each answer must rest on, the freshness bound
(hours), and the cost bound. The card is serialized canonically and
SHA-256 sealed; any post-seal edit — a loosened bound, a dropped
required element, a reworded question — changes the hash and is
detected by :func:`verify_seal`. Nobody moves the goalposts after
seeing results, including the builder.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime

SEAL_ALGORITHM = "sha256(canonical-json-v1)"


def _finite_number(value) -> bool:
    """JSON criteria must be real usable numbers, never bool/NaN/infinity."""
    return (isinstance(value, int) and not isinstance(value, bool)) or (
        isinstance(value, float) and math.isfinite(value)
    )


def _is_parseable_ts(value) -> bool:
    """True iff ``value`` is a string holding a parseable ISO-8601
    timestamp ('Z' suffix accepted)."""
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def canonical(obj) -> str:
    """Canonical JSON form used for sealing (same discipline as the
    Excavator chain: sorted keys, tight separators)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def validate_card(card: dict) -> None:
    """Raise ValueError unless ``card`` is a well-formed task card."""
    if not isinstance(card, dict):
        raise ValueError("task card must be a JSON object")
    if not card.get("id"):
        raise ValueError("task card needs an 'id'")
    bound = card.get("freshness_bound_hours")
    if not _finite_number(bound) or bound <= 0:
        raise ValueError("task card needs a positive finite numeric 'freshness_bound_hours'")
    cost = card.get("cost_bound")
    if not isinstance(cost, dict) or not all(
        _finite_number(cost.get(k)) and cost[k] >= 0
        for k in ("max_credits", "max_tokens")
    ):
        raise ValueError(
            "task card needs 'cost_bound' with non-negative finite numeric max_credits and max_tokens"
        )
    questions = card.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("task card needs a non-empty 'questions' list")
    seen = set()
    for q in questions:
        if not isinstance(q, dict) or not q.get("id") or not q.get("question"):
            raise ValueError("each question needs an 'id' and 'question'")
        if q["id"] in seen:
            raise ValueError(f"duplicate question id: {q['id']}")
        seen.add(q["id"])
        elements = q.get("required_elements")
        if not isinstance(elements, list) or not elements or not all(
            isinstance(e, str) and e for e in elements
        ):
            raise ValueError(
                f"question {q['id']} needs a non-empty 'required_elements' list of strings"
            )
        if "freshness_bound_hours" in q:
            fb = q["freshness_bound_hours"]
            if not _finite_number(fb) or fb <= 0:
                raise ValueError(
                    f"question {q['id']} freshness_bound_hours must be positive finite numeric"
                )


def seal_card(card: dict) -> str:
    """Return the SHA-256 seal of a task card's canonical form."""
    validate_card(card)
    return hashlib.sha256(canonical(card).encode("utf-8")).hexdigest()


def seal_task_card(card: dict, sealed_at: str) -> dict:
    """Return a sealed task-card envelope: {card, seal, sealed_at, ...}."""
    return {
        "card": card,
        "seal": seal_card(card),
        "sealed_at": sealed_at,
        "seal_algorithm": SEAL_ALGORITHM,
    }


def verify_seal(sealed: dict) -> bool:
    """True iff the envelope is complete AND its seal recomputes
    from its card exactly.

    Completeness (Session 1.1, audit fix F5): the envelope must
    carry a ``sealed_at`` that parses as a timestamp and a
    ``seal_algorithm`` equal to the supported value — an envelope
    stripped of its metadata is malformed and verifies as False,
    exactly like an edited card. Any post-seal edit to the card —
    however small — also fails this check. A malformed envelope
    verifies as False, never raises.
    """
    try:
        if not isinstance(sealed, dict):
            return False
        card = sealed["card"]
        expected = sealed["seal"]
        if sealed.get("seal_algorithm") != SEAL_ALGORITHM:
            return False
        if not _is_parseable_ts(sealed.get("sealed_at")):
            return False
        validate_card(card)
    except (KeyError, TypeError, ValueError):
        return False
    return hashlib.sha256(canonical(card).encode("utf-8")).hexdigest() == expected


def freshness_bound_for(card: dict, question_id: str):
    """The freshness bound (hours) governing one question: its own
    override when present, else the card-level bound."""
    for q in card["questions"]:
        if q["id"] == question_id:
            return q.get("freshness_bound_hours", card["freshness_bound_hours"])
    return card["freshness_bound_hours"]
