# HAND-OFF — Scoring Layer, Session 2: claim-support grader (builder seat)

**From:** Stephen Luc, via Tally Muse · 2026-10-27 night
**Seat:** a fresh Astra Ultra session, builder. Lane sub-agents as you see fit; nobody certifies their own work.

## The job

The Scoring Layer (enclosed, `scoring-layer/`) grades an agent's web-research answers. Session 1 (built, audited, fix round applied) shipped four deterministic graders. **Session 2 adds the claim-support grader**, specified in `scoring-layer/BUILD-SHEET.md` under "Session 2 — claim-support grader":

- Extract the factual claims from the agent's final answer.
- Bind each claim to the fetched evidence it cites.
- Return a verdict per claim — **SUPPORTED / UNSUPPORTED / CONTRADICTED** — with the supporting passage shown, or its absence declared on the record. A judge seat may be used for the residue that deterministic checks cannot settle; judge rows are labeled JUDGE and never blended into deterministic marks.
- The run record already carries a `claims: []` placeholder waiting for this. The planted grader-error beat gets its claim-support form here (see BUILD-SHEET).

Also in scope, behind the same run-record schema: **live capture** — real Firecrawl reads through `capture.py`. **FREE TIER ONLY.** Any spend, credit purchase, or paid route needs Stephen's explicit word first; at a limit, work waits, it never charges.

The task pack (gold tasks with gold reads) arrives separately from the Opus seat as data — task-card + fixture/live-capture files. Build Session 2 so the pack plugs in as data with **no core changes**.

## State of the enclosed code (honest)

Session 1: 49/49 tests (26 original + 23 regression tests named after an independent audit's findings — read `scoring-layer/PROGRESS.md`, Session 1.1 entry). The fix round's **independent re-audit is still pending**: build on the interfaces as they stand; if behavior contradicts the BUILD-SHEET, that's a finding — report it with receipts, don't silently work around it.

## Stephen's Laws (binding)

Build + test + self-review; an independent seat certifies afterward — not you. Work from this hand-off and the BUILD-SHEET verbatim. Test at the surface the user touches. Intent unclear → ask, don't guess. Every claim in your report carries receipts (test output, run logs, hashes); unknown = UNKNOWN, unmeasured = labeled. Subscriptions only, no pay-as-you-go anywhere.

## Report back

Per-part results against the BUILD-SHEET's Session 2 description; test counts before/after; the claims placeholder wired end-to-end on the enclosed fixture; one live-capture run on the free tier with its receipts, or an honest statement of what blocked it. Candidate as one zip with manifest + SHA-256. Nothing published or sent.
