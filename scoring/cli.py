"""Receipt-first CLI for synthetic replay and free-only live capture.

``run`` uses Session 2 by default; ``--session1`` replays the historical
four-grader pipeline. All input grading and review-decision validation
complete before a chain is changed or a scorecard is printed. Supplied
Session 1 evidence stays in data/chain.jsonl; new default runs write their
own data/chain-session2.jsonl. No network operation is implicit in grading.
"""

from __future__ import annotations

import argparse
import copy
import json
import shlex
import sys
from pathlib import Path

from .capture import load_fixture, validate_run
from .chain import Store
from .graders import grade_run, grade_session2_run
from .precision import compute_precision, decisions_from_chain
from .scorecard import render_precision, render_scorecard
from .sealing import canonical, seal_task_card, verify_seal

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FIXTURE = ROOT / "fixtures" / "synthetic_firecrawl.json"
DEFAULT_CHAIN = ROOT / "data" / "chain.jsonl"
SESSION2_CHAIN = ROOT / "data" / "chain-session2.jsonl"
FIXTURE_SEALED_AT = "2026-10-27T15:55:00Z"


def _refuse_unverified(store: Store, command: str) -> int | None:
    if not store.path.exists():
        return None
    verdict = store.verify_chain()
    if verdict["ok"]:
        return None
    detail = verdict.get("error") or f"first_bad_seq={verdict['first_bad_seq']}"
    print(f"ERROR: {command}: chain verification failed ({detail}) — "
          "refusing to produce a score from unverified evidence", file=sys.stderr)
    return 1


def _unique_flags(flags: list[dict]) -> list[dict]:
    ids = [flag["flag_id"] for flag in flags]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate flag_id in evidence; precision would be ambiguous")
    return flags


def _precision_text(decisions, flags, session2=False):
    """Do not blend JUDGE precision into deterministic marks."""
    compute_precision(decisions, flags)  # validates the whole set first
    if not session2:
        return render_precision(compute_precision(decisions, flags))
    parts = []
    for method, predicate in (
        ("DETERMINISTIC", lambda grader: grader != "claim-support-judge"),
        ("JUDGE", lambda grader: grader == "claim-support-judge"),
    ):
        selected_flags = [f for f in flags if predicate(f["grader"])]
        selected_decisions = [d for d in decisions if predicate(d["grader"])]
        parts.append(f"{method} REVIEW PRECISION (separate method ledger)")
        parts.append(render_precision(compute_precision(selected_decisions, selected_flags)))
    return "\n".join(parts)


def _load_pack(path, session1=False):
    if session1:
        return load_fixture(path)
    # Delayed import allows the historical fixture API to remain usable.
    from .capture import load_task_pack
    return load_task_pack(path)


def _prepare(pack: dict, store: Store | None, session1=False):
    """Return fully validated artifacts without changing the chain."""
    card = pack["task_card"]
    runs = pack["runs"]
    if not isinstance(runs, list) or not runs:
        raise ValueError("task pack needs a non-empty runs list")
    sealed = pack.get("sealed_task_card")
    if sealed is not None:
        if not verify_seal(sealed) or canonical(sealed["card"]) != canonical(card):
            raise ValueError("task-pack sealed_task_card does not verify or match task_card")
    else:
        if pack.get("synthetic") is False or any(r.get("synthetic") is not True for r in runs):
            raise ValueError("live task pack requires the original sealed_task_card")
        sealed = seal_task_card(card, pack.get("sealed_at", FIXTURE_SEALED_AT))
    if not verify_seal(sealed):
        raise ValueError("task-card seal does not verify")
    run_ids = [r.get("run_id") for r in runs]
    if len(run_ids) != len(set(run_ids)):
        raise ValueError("duplicate run_id in task pack")
    existing = list(store.iter_records()) if store is not None and store.path.exists() else []
    old_run_ids = {r["payload"].get("run", {}).get("run_id")
                   for r in existing if r["type"] == "run"}
    for run_id in run_ids:
        if run_id in old_run_ids:
            raise ValueError(f"run_id {run_id!r} already exists in this chain; use a new chain or run ID")
    for record in existing:
        if record["type"] != "task_card":
            continue
        old = record["payload"].get("sealed", {})
        if old.get("card", {}).get("id") == card["id"] and old.get("seal") != sealed["seal"]:
            raise ValueError(f"task card {card['id']!r} already exists with a different seal")
    prepared = []
    for run in runs:
        validate_run(run, allow_unknown_spend=(run.get("synthetic") is False or
                     run.get("capture_origin") == "firecrawl-keyless-v1"))
        if run["task_card_id"] != card["id"]:
            raise ValueError("run task_card_id does not match task_card")
        if "capture_receipts" in pack:
            run["capture_evidence"] = {
                "capture_status": pack["capture_status"],
                "receipts": copy.deepcopy(pack["capture_receipts"]),
            }
        result = (grade_run(run, card) if session1 else
                  grade_session2_run(run, card, judge_decisions=run.get("judge_decisions")))
        if not session1:
            # The seal travels with both the exact captured run and its verdict.
            result["task_card_seal"] = sealed["seal"]
            run["task_card_seal"] = sealed["seal"]
        prepared.append((run, result))
    all_flags = _unique_flags([flag for _run, result in prepared for flag in result["flags"]])
    decisions = pack.get("human_decisions", [])
    compute_precision(decisions, all_flags)
    return sealed, prepared, decisions, all_flags


def cmd_run(args) -> int:
    session1 = bool(args.session1)
    chain = args.chain or str(DEFAULT_CHAIN if session1 else SESSION2_CHAIN)
    store = Store(chain)
    refusal = _refuse_unverified(store, "run")
    if refusal is not None:
        return refusal
    pack = _load_pack(args.pack, session1)
    sealed, prepared, decisions, all_flags = _prepare(pack, store, session1)
    # Nothing before this line mutates persistent evidence or prints a score.
    card_rec = store.append("task_card", {"sealed": sealed})
    renders = []
    for run, result in prepared:
        run_rec = store.append("run", {"run": run})
        verdict_rec = store.append("verdicts", {"grade": result})
        renders.append(render_scorecard(sealed, run, result, {
            "task_card": card_rec["seq"], "run": run_rec["seq"], "verdicts": verdict_rec["seq"]}))
    chained_decisions = []
    for decision in decisions:
        rec = store.append("queue_decision", decision)
        chained_decisions.append({**decision, "seq": rec["seq"]})
    verdict = store.verify_chain()
    if not verdict["ok"]:
        print("ERROR: chain verification failed after append; no score printed", file=sys.stderr)
        return 1
    print("Session 1 compatibility replay" if session1 else "Session 2 claim-support pipeline")
    print(f"Task card sealed: {sealed['seal']}")
    print(f"  appended to chain as seq {card_rec['seq']}")
    for rendered in renders:
        print("\n" + rendered)
    if decisions:
        print("\nSYNTHETIC REVIEW DECISIONS (labeled fixture data; not actual human reviews):"
              if all(run.get("synthetic") for run, _result in prepared) else
              "\nREVIEW DECISION RECEIPTS:")
    print(_precision_text(chained_decisions, all_flags, session2=not session1))
    print(f"\nChain after run: {verdict['records']} records, verify ok={verdict['ok']}")
    return 0


def cmd_verify(args) -> int:
    path = args.chain or str(SESSION2_CHAIN)
    verdict = Store(path).verify_chain()
    print(f"Chain {path}: {verdict['records']} records, "
          f"ok={verdict['ok']}, first_bad_seq={verdict['first_bad_seq']}")
    if verdict.get("error"):
        print(f"  error: {verdict['error']}")
    return 0 if verdict["ok"] else 1


def cmd_precision_demo(args) -> int:
    chain = args.chain or str(SESSION2_CHAIN if args.session2 else DEFAULT_CHAIN)
    store = Store(chain)
    refusal = _refuse_unverified(store, "precision-demo")
    if refusal is not None:
        return refusal
    chained = decisions_from_chain(store) if store.path.exists() else []
    stored_verdicts = list(store.iter_records(type="verdicts")) if store.path.exists() else []
    session2 = args.session2 or any(r["payload"]["grade"].get("session") == 2 for r in stored_verdicts)
    if stored_verdicts:
        flags = _unique_flags([flag for r in stored_verdicts
                               for flag in r["payload"]["grade"]["flags"]])
        decisions = chained
        source = "verified chain verdicts and queue_decision records"
        stored_runs = list(store.iter_records(type="run"))
        if stored_runs and all(r["payload"]["run"].get("synthetic") is True for r in stored_runs):
            source += " (SYNTHETIC fixture demonstration; invented review decisions)"
    else:
        pack = _load_pack(args.pack, session1=not args.session2)
        _sealed, _prepared, decisions, flags = _prepare(pack, None, session1=not args.session2)
        source = "SYNTHETIC fixture demonstration (invented review decisions)"
    # Validate before even a precision heading is printed.
    rendered = _precision_text(decisions, flags, session2=session2)
    print(f"Precision from {source}:")
    print(rendered)
    return 0


def cmd_capture_live(args) -> int:
    from .live import capture_live_task_pack
    packet = capture_live_task_pack(args.pack, args.output, timeout=args.timeout)
    print(f"Live capture status: {packet['capture_status']}")
    print(f"Capture receipt: {args.output}")
    for error in packet.get("capture_errors", []):
        print("  " + (error if isinstance(error, str) else json.dumps(error, sort_keys=True)))
    if packet["capture_status"] == "COMPLETE":
        print("Grade the captured data with: python3 -m scoring.cli run --pack "
              + shlex.quote(str(args.output)) + " --chain <new-chain-path>")
        return 0
    return 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="scoring.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("run", help="grade a synthetic or captured task pack (Session 2 default)")
    p.add_argument("--fixture", "--pack", dest="pack", default=str(DEFAULT_FIXTURE))
    p.add_argument("--chain")
    p.add_argument("--session1", action="store_true", help="historical four-grader compatibility replay")
    p = sub.add_parser("precision-demo", help="precision from verified decisions; legacy default")
    p.add_argument("--fixture", "--pack", dest="pack", default=str(DEFAULT_FIXTURE))
    p.add_argument("--chain")
    p.add_argument("--session2", action="store_true", help="separate DETERMINISTIC/JUDGE ledgers")
    p = sub.add_parser("verify")
    p.add_argument("--chain")
    p = sub.add_parser("capture-live", help="explicit keyless free Firecrawl capture; no paid fallback")
    p.add_argument("--pack", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--timeout", type=float, default=45)
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            return cmd_run(args)
        if args.command == "verify":
            return cmd_verify(args)
        if args.command == "capture-live":
            return cmd_capture_live(args)
        return cmd_precision_demo(args)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
