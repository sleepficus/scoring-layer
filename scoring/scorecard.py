"""Run scorecard rendering (text, Session 1).

Scorer doctrine: per-dimension numbers only, no composite, and every
number is printed WITH its receipts under it — the flags with their
evidence, the per-fetch spend, the per-element presence lists. A
reader never has to trust a number they cannot open.
"""

from __future__ import annotations

import json


def _fmt(value) -> str:
    return "n/a" if value is None else str(value)


def render_scorecard(sealed: dict, run: dict, result: dict,
                     chain_seqs: dict | None = None) -> str:
    card = sealed["card"]
    lines = ["=" * 72, "SCORING LAYER — RUN SCORECARD"]
    if run.get("synthetic"):
        lines.append("DATA: SYNTHETIC FIXTURE — invented pages, prices, and responses. Not real Firecrawl output.")
    else:
        lines.append("DATA: LIVE CAPTURE — captured provider fields; UNKNOWN means unreported evidence.")
    lines.extend([
        f"Run:        {run['run_id']}  (agent: {run['agent_label']})",
        f"Task card:  {card['id']} — {card.get('title', '')}",
        f"Card seal:  {sealed['seal']}  (sealed {sealed['sealed_at']})",
        f"Started at: {run['started_at']}",
    ])
    if chain_seqs:
        lines.append("Chain:      " + ", ".join(f"{k} seq {v}" for k, v in chain_seqs.items()))
    deterministic_flags = sum(f["grader"] != "claim-support-judge" for f in result["flags"])
    judge_flags = len(result["flags"]) - deterministic_flags
    lines.append(f"Flags: DETERMINISTIC {deterministic_flags}; JUDGE {judge_flags} "
                 "(each receipt below; no composite score)")
    for name, dim in result["dimensions"].items():
        lines.extend(["", f"-- {name} (grader: {dim['grader']}) --"])
        if name == "Fetch truth":
            lines.append(f"Relied-on fetches: {dim['relied_on_fetches']} of {dim['total_fetches']} total; flags: {dim['flag_count']}")
        elif name == "Freshness":
            lines.append(f"Sealed freshness bound: {dim['bound_hours']}h; flags: {dim['flag_count']}")
        elif name == "Completeness":
            lines.append(f"Required elements: {dim['required_elements']}; present: {dim['present_elements']}; "
                         f"missing: {dim['missing_elements']}; flags: {dim['flag_count']}")
            for qid, detail in dim["detail"].items():
                lines.append(f"  {qid}: present={detail['present']}")
                lines.append(f"  {qid}: missing={detail['missing']}")
        elif name == "Cost truth":
            cost = dim["cost"]
            credits = "UNKNOWN" if cost["total_credits"] is None else str(cost["total_credits"])
            tokens = "UNKNOWN" if cost["total_tokens"] is None else str(cost["total_tokens"])
            lines.append(f"Credits spent: {credits} (bound {cost['cost_bound']['max_credits']}); "
                         f"tokens spent: {tokens} (bound {cost['cost_bound']['max_tokens']})")
            lines.append(f"Historical Session 1 denominator — required elements found in consumed content: "
                         f"{cost['verified_facts']} of {cost['required_facts']}; "
                         f"credits per present element: {_fmt(cost['credits_per_verified_fact'])}; "
                         f"tokens per present element: {_fmt(cost['tokens_per_verified_fact'])}")
            for fetch in cost["per_fetch"]:
                lines.append(f"  {fetch['url']}: {_fmt(fetch['creditsUsed'])} credits, {_fmt(fetch['tokensUsed'])} tokens")
            if "claim_cost" in result:
                claim_cost = result["claim_cost"]
                lines.append(claim_cost["scope"])
                for method in ("deterministic", "judge"):
                    entry = claim_cost[method]
                    lines.append(f"  {method.upper()} supported-claim denominator: {entry['supported_claims']}; "
                                 f"credits per supported claim: {_fmt(entry['credits_per_supported_claim'])}; "
                                 f"tokens per supported claim: {_fmt(entry['tokens_per_supported_claim'])}")
            lines.append(f"Flags: {dim['flag_count']}")
        elif name == "Claim support":
            for method in ("deterministic", "judge"):
                summary = dim[method]
                lines.append(f"{method.upper()}: {summary['SUPPORTED']} SUPPORTED; "
                             f"{summary['UNSUPPORTED']} UNSUPPORTED; {summary['CONTRADICTED']} CONTRADICTED; "
                             f"{summary['total']} total")
            lines.append("Extraction receipt: " + json.dumps(dim.get("extraction", {}), sort_keys=True))
            for row in dim["claims"] + dim.get("judge_claims", []):
                lines.append(f"  {row['method']} {row['claim_id']}: {row['verdict']}")
                lines.append(f"    answer: {row['text']}")
                lines.append(f"    answer span: {json.dumps(row['answer_span'], sort_keys=True)}; "
                             f"answer SHA-256: {row['answer_sha256']}")
                lines.append("    citations: " + json.dumps(row["citations"], sort_keys=True))
                lines.append(f"    reason: {row['reason']}")
                for passage in row.get("passages", []):
                    lines.append("    passage receipt: " + json.dumps(passage, sort_keys=True))
                if row.get("absence") is not None:
                    lines.append("    absence: " + json.dumps(row["absence"], sort_keys=True))
                if row.get("binding_errors"):
                    lines.append("    citation binding errors: " + json.dumps(row["binding_errors"], sort_keys=True))
                if row.get("judge"):
                    lines.append("    judge provenance: " + json.dumps(row["judge"], sort_keys=True))
        for flag in dim["flags"]:
            lines.extend([
                f"  FLAG {flag['flag_id']}",
                f"    criterion: {flag['criterion']}",
                f"    subject:   {flag['subject']}",
                "    evidence:  " + json.dumps(flag["evidence"], sort_keys=True),
            ])
    if result.get("session") != 2:
        lines.extend(["", "Session 1 compatibility: claim-support grading was not run."])
    lines.append("=" * 72)
    return "\n".join(lines)


def render_precision(precision: dict) -> str:
    lines = ["GRADER PRECISION (from human confirm/kill decisions)"]
    for grader, entry in sorted(precision["per_grader"].items()):
        pct = ("UNVERIFIED — no decisions yet" if entry["precision"] is None
               else f"{entry['precision']:.1%}")
        lines.append(
            f"  {grader}: precision {pct} "
            f"({entry['confirmed']} confirmed, {entry['killed']} killed, "
            f"{entry['pending']} pending)"
        )
    overall = precision["overall"]
    pct = ("UNVERIFIED — no decisions yet" if overall["precision"] is None
           else f"{overall['precision']:.1%}")
    lines.append(
        f"  OVERALL: precision {pct} "
        f"({overall['confirmed']} confirmed, {overall['killed']} killed, "
        f"{overall['pending']} pending)"
    )
    receipts = precision.get("receipts") or []
    if receipts:
        # Every number drills to its receipts (Scorer doctrine): the
        # individual decisions under the precision figures, each with
        # the chain sequence it came from when it has one.
        lines.append("  Decision receipts:")
        for r in receipts:
            origin = (f"chain seq {r['seq']}" if r.get("seq") is not None
                      else "fixture data (no chain seq)")
            line = (f"    - {r['flag_id']} · grader {r['grader']} · "
                    f"{r['decision']} · {origin}")
            if r.get("note"):
                line += f" · note: {r['note']}"
            lines.append(line)
    return "\n".join(lines)
