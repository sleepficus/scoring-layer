# Scoring Layer — BUILD SHEET

House artifact: a **house-neutral live scoring layer for agent work**.
Firecrawl is the first skin (task pack), not the product. Spec:
`~/workspace/goals/remote-job-hunt/files/scoring-demo-spec-2026-10-27.md`
(commissioned by Stephen 2026-10-27 ~16:32 EDT; commission record is
appended to the spec).

## Architecture

- **Language/runtime:** Python 3.12, **standard library only** — zero
  external dependencies. Basis: the Excavator proved this discipline on
  both VM and Mac; the artifact must run anywhere Stephen's seats run
  without an install step. Any future dependency must be justified in
  writing here before it lands.
- **Shape:** a small package (`scoring/`) + fixtures + a hash-chained
  evidence store of its own. It borrows the Excavator's chain
  *discipline and format* (seq / ts / type / prev_hash / hash / payload,
  `hash = sha256(prev_hash + canonical(payload))`, genesis `"0"*64`)
  but writes only to its own chain at `data/chain.jsonl`. It never
  reads-for-writing or modifies the Excavator.
- **Scorer doctrine (binding):** no naked composite score anywhere.
  Every number on every surface drills to its receipts — the flag, the
  fetched document, the sealed criterion it was graded against.

## Module map (Session 1)

| Module | Job |
|---|---|
| `scoring/sealing.py` | Task-card schema validation, SHA-256 sealing of the canonical card, seal verification (any post-seal edit detected). |
| `scoring/capture.py` | Run-record schema + validation; fixture loader that normalizes Firecrawl-*shaped* responses into run records. |
| `scoring/graders.py` | The four deterministic graders: fetch-truth, freshness, completeness, cost truth. Each emits flags with evidence receipts. |
| `scoring/chain.py` | Append-only hash-chained JSONL store (Excavator-compatible format, own file). Record types: `task_card`, `run`, `verdicts`, `queue_decision`. |
| `scoring/precision.py` | Grader-precision scorecard math from human confirm/kill decisions (per grader + overall). |
| `scoring/scorecard.py` | Text scorecard renderer: per-dimension results, every number with its receipts listed under it. |
| `scoring/cli.py` | `run` (grade fixtures end-to-end), `verify` (chain check), `precision-demo` (precision math on fixture decisions). |

## Session plan

- **Session 1 (this session) — deterministic core.** Sealing, capture
  schema + labeled synthetic fixtures, the four deterministic graders,
  the evidence chain, precision math, CLI scorecard, test suite.
  No judge, no claim support, no network, no Firecrawl account, no
  spend. Fixtures only.
- **Session 2 — claim-support grader.** Claim extraction from the
  agent's final answer, citation binding, judge-seat verdicts
  SUPPORTED / UNSUPPORTED / CONTRADICTED with the passage shown or its
  absence declared. The run record already carries a `claims`
  placeholder for this. (Also: the planted grader-error beat gets its
  claim-support form here; Session 1's fixture already plants one at
  the completeness layer — a formatting-variant flag a human kills.)
- **Nov 1 — task pack (REASSIGNED 2026-10-27).** ~~Fable authors~~ —
  Stephen corrected 2026-10-27: the credit carrying the Fable API seat
  expires Oct 27, so no Fable seat exists after today (a live probe the
  same hour also confirmed the Anthropic API is blocked by Stephen's
  own usage limit until 2026-11-01 00:00 UTC). The OPUS seat authors
  the real Firecrawl-skin task pack instead: gold tasks, gold reads,
  freshness bounds, adversarial cases. Stephen's standing assessment,
  recorded with the change: Fable was the strongest auditor in the
  yard and the best at finding ways around difficult things — Opus
  covers the work, but audits lose Fable's particular second read. Plugs in as new task-card + fixture/live-capture files; no
  core changes expected. Live capture (real Firecrawl calls, free tier
  only — any spend still needs Stephen's explicit word) lands with
  the task pack, behind `capture.py`'s same run-record schema.
- **Later — queue UI polish.** The review queue as a page (flags live,
  one-click confirm/kill writing `queue_decision` records back to the
  chain; decisions feed `precision.py`). Session 1 ships the math and
  the record type, not the page.
- **Later — rehearsal / film.** The spec §5 three-minute shape:
  sealed card, live run graded as it happens, queue beat with the
  planted grader error, closing scorecard with grader precision on it.

## Design decisions made in Session 1 (builder's plumbing, logged)

1. **unittest, not pytest** — pytest is not installed on this VM
   (verified 2026-10-27); stdlib unittest keeps the zero-dependency
   rule honest.
2. **Fixture URLs use the `.invalid` TLD** and every fixture page,
   price, and limit is invented, so synthetic data cannot be mistaken
   for a real site or real Firecrawl output even out of context.
3. **Freshness is graded only for fetches the agent relied on** — a
   stale page the agent fetched but did not use cannot mislead an
   answer, and flagging it would cry wolf (grader precision is a
   published number in this design; flags must earn their place).
4. **Cost truth reports credits and tokens separately**, never summed
   into one unit, and computes cost *per verified fact* for each.
   Verified facts = required elements (from the sealed card) found
   present by the completeness grader — the one honest denominator
   available deterministically.
5. **The completeness grader matches required elements as
   case-insensitive substrings.** Deliberately naive in v1: the
   fixture's planted kill (required "1,200 requests" vs. content
   "1200 requests") is exactly the class of false flag this produces,
   and the precision scorecard exists to make that cost visible.


## Session 2 implementation record — 2026-10-28

The exact night hand-off is preserved at `handoff/HANDOFF.md`. Its newer scope includes both claim support and real free-tier capture in this session, with the queue UI and independent Opus gold pack still later. Stephen’s direct request selected Sol 6.1 Ultra lanes instead of the hand-off’s proposed Astra builder seat.

- `scoring/claims.py`: conservative factual prose candidates with exact answer spans, explicit captured citation binding, passage offsets and hashes, SUPPORTED / UNSUPPORTED / CONTRADICTED rows; optional external judge decisions in a separate JUDGE ledger. No model calls or dependencies.
- `scoring/capture.py`: legacy synthetic loader plus `load_task_pack`; citation/judge metadata preserved. Synthetic missing spend remains rejected.
- `scoring/live.py`: fixed keyless free Firecrawl scrape, pre-call durable request receipt, original response bytes and hash, sealed task card and complete-plan validation. Unknown metering is preserved. No API key, auto retry, paid fallback or purchase.
- `graders.py`, `scorecard.py`, `cli.py`: Session 2 pipeline populates claims before chaining, validates the full batch before writing, prints separate deterministic/judge support, cost denominators and precision. Historical Session 1 behavior remains under explicit `--session1` / `grade_run`.
- `fixtures/session2_claim_support.json`: cited synthetic examples and the planted semantic false flag (monthly/per month). Invented confirm/kill decisions visibly move demo precision from 100% to 66.7%; this is demonstration data, not an actual human review or measured real-world precision.
- `fixtures/session2_judge_demo.json`: separate synthetic judge import resolves semantic residue without altering deterministic marks.
- `fixtures/live_keyless_example_plan.json`: one public-page capture plan; the real result and byte receipts are preserved in `receipts/live-keyless-capture.json`.

Plumbing decisions: explicit citations are mandatory for claim support; legacy question IDs cannot silently fabricate citations. Numbers missing from live provider metadata remain UNKNOWN while strict synthetic input validation stays unchanged. Cost truth’s historical count of found task elements is labeled as such, beside separate supported-claim denominators; answer-generation and separate judge costs are unmeasured. The live read harness accepts a caller-supplied answer and does not claim to be an autonomous research-agent loop.

Runtime verified: Python3.12.7 and macOS Python3.9.6, stdlib only. Source/receipt hashes, test results, self-review and independent audit are reported separately under `receipts/` and `RESULTS.md`.


### Session 2 audit repair decisions

Source qualification markers are retained when evaluating support; unresolved note context is explicit semantic residue. Exact decimal arithmetic compares scalar values without deleting raw evidence spellings. Factual Markdown headings participate in extraction, and trailing sentence citations are consumed so they cannot be borrowed by the next sentence. Sealed freshness and cost criteria require finite, non-boolean numbers. These are focused corrections to the independent A1–A5 findings, not additions to product scope.


Historical note: the original architecture paragraph’s v1 hash formula was superseded by Session 1.1. Current v2 hashes cover seq, ts, type, prev_hash and payload; the supplied chain is v2 and is preserved unchanged. Session 2 independent closure is recorded in receipts/audit/CLOSURE.md.
