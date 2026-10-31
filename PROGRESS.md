# Scoring Layer — PROGRESS

## Session 1 — deterministic core (2026-10-27)

Built per `BUILD-SHEET.md` and the spec's commission record
(Stephen, 2026-10-27 ~16:32 EDT). Scope honored exactly: deterministic
core only — no judge/claim-support (Session 2), no Firecrawl account,
no API keys, no network calls, no spend. Fixtures only, labeled
synthetic everywhere they surface.

### What was built

- `scoring/sealing.py` — task-card validation, canonical SHA-256
  sealing, seal verification (any post-seal edit detected).
- `scoring/capture.py` — run-record schema + validation; fixture
  loader normalizing Firecrawl-shaped responses; **refuses any
  fixture file not labeled synthetic**; every run record carries
  `synthetic: True` and a `claims: []` placeholder with a Session 2
  note.
- `scoring/graders.py` — the four deterministic graders:
  fetch-truth (non-200 relied-on documents + block/challenge
  content-shape heuristic), freshness (cachedAt vs. the sealed bound,
  per-question overrides honored), completeness (sealed required
  elements vs. consumed content), cost truth (captured credits/tokens
  ÷ verified facts, sealed cost bound enforced; units never summed).
- `scoring/chain.py` — own append-only hash-chained JSONL store,
  format-compatible with the Excavator's discipline (read, not
  touched — the Excavator's chain and files were not modified).
  Record types: `task_card`, `run`, `verdicts`, `queue_decision`.
- `scoring/precision.py` — grader-precision math from human
  confirm/kill decisions, per grader + overall; no decisions =
  precision None (UNVERIFIED), never 100%.
- `scoring/scorecard.py` + `scoring/cli.py` — `run` / `verify` /
  `precision-demo`; the scorecard prints per-dimension numbers with
  their flags, evidence, per-element lists, and per-fetch spend
  under each. No composite score exists anywhere in the output.
- `fixtures/synthetic_firecrawl.json` — invented company
  (WidgetForge), invented prices/limits, `.invalid` URLs, two runs:
  a clean run (0 flags) and a failure run (403-as-document, 7-hour
  cache vs. 1-hour sealed bound, missing elements). Five labeled
  demo human decisions, including the **planted grader error**: the
  completeness flag on "1,200 requests" (content carried "1200
  requests") is killed, taking completeness precision to 66.7% on
  the demo scorecard — the spec §4 honesty beat, present from
  Session 1 in completeness form.

### Test receipts

- `python3 -m unittest discover -s tests -v` — **26 tests run,
  26 passed, 0 failed** (exit 0). Coverage includes: 403-as-document
  catch; block page under a 200 caught by content shape; unrelied
  fetches not flagged; 7-hour cache vs. 1-hour bound (age_hours
  evidence = 7.0); clean run = 0 flags across all dimensions; seal
  tamper detection (question text, freshness bound, required
  element, seal value); chain append/verify + tampered-payload
  detection at the right seq; precision math on known confirm/kill
  sets (incl. per-grader 2/3, overall 1/2, empty = None); the
  fixture demonstration numbers (overall precision 0.8); the planted
  formatting-variant flag pinned by test so the demo beat cannot
  silently disappear; unlabeled fixture data refused.
- `python3 -m scoring.cli run` — exit 0. Card seal
  `0558af83a81cac2163dd0dc0ed6ed4fade3880f79ec89bbba333fdb238adc784`;
  clean run 0 flags; failure run 5 flags (fetch-truth 1, freshness 1,
  completeness 3, cost 0); precision demo: completeness 66.7%,
  fetch-truth 100%, freshness 100%, overall 80.0% (4 confirmed,
  1 killed). Chain: **10 records, verify ok=True**.
- `python3 -m scoring.cli verify` — ok=True, first_bad_seq=None.
- `python3 -m scoring.cli precision-demo` — reads the decisions back
  from the chain's queue_decision records; same numbers as above.

### Self-review notes (Law 2 — builder's lap)

- Re-read every grader against the spec §2 table after the tests
  passed: fetch-truth, freshness, completeness, cost truth all map;
  claim support and extraction fidelity are correctly absent
  (Session 2 / task-pack territory), and the scorecard says so on
  its face rather than leaving a silent gap.
- Checked the Scorer doctrine by reading the actual CLI output, not
  the code: every dimension prints its receipts inline; the words
  "total flags" appear once as a count of flags (each listed below),
  not as a score. No composite, no letter grade, no 0–100.
- Confirmed the synthetic label survives the whole path: fixture
  file warning → loader enforcement → run record `synthetic: True`
  → scorecard banner → PROGRESS/README wording.
- Known v1 naivety, stated rather than hidden: completeness matching
  is case-insensitive substring only (the planted kill is its honest
  cost); the block-marker list is a small conservative set, not a
  classifier; freshness grades relied-on fetches only (decision
  logged in BUILD-SHEET.md).

### Law 2 state

Builder built, tested, and self-reviewed (above). **Independent
audit certification is OUTSTANDING** — per the spec §7 it belongs to
a later session (an auditor seat that did not build it re-runs the
gold tasks and attacks the grader), sequenced in the Nov 1 program.
Nothing here is certified, shipped, or published.

### Session 2 handoff list

1. Claim-support grader: extract claims from `final_answer` into the
   run record's `claims` placeholder; bind each claim to the fetched
   passage that must carry it; judge-seat verdicts SUPPORTED /
   UNSUPPORTED / CONTRADICTED with the passage shown or its absence
   declared. The failure fixture's final answer already contains an
   unsupported price claim waiting for it.
2. The planted grader-error beat gets its claim-support form (spec
   §5) alongside Session 1's completeness form.
3. Queue decisions stop being fixture data: a human confirm/kill in
   the queue UI appends `queue_decision` records (type and math
   already shipped); precision reads them via
   `precision.decisions_from_chain`.
4. Nov 1, in parallel: the Opus seat's task pack (gold tasks/reads,
   adversarial cases) and the live capture harness behind
   `capture.py`'s schema — free tier only; any spend needs Stephen's
   explicit word (#5 remains undecided). [Corrected 2026-10-27 in
   Session 1.1 (audit finding F7): this item originally named Fable;
   BUILD-SHEET.md reassigned the task pack to the Opus seat. See the
   Session 1.1 entry below.]

## Session 1.1 — audit fix round (2026-10-27)

Harbor's independent audit of Session 1 returned **FAIL** (verdict:
"the evidence path can change the reported score while verification
reports success"). The advertised demo numbers were all confirmed
(26/26 tests, 0/5 flags, 80.0% precision independently recomputed,
the planted naive matcher honestly documented, fixture enforcement
real); the failure was evidence integrity, findings F1–F7. This
session fixed each finding. The builder did not re-audit its own
work: certification of these fixes belongs to a fresh auditor seat.

### Findings addressed

- **F1 (High) — chain hash covered only prev_hash + payload.**
  `scoring/chain.py` is now format **v2**: the record hash covers
  `seq`, `ts`, `type`, `prev_hash`, and `payload` under canonical
  serialization, and every record carries `hash_version: 2`.
  Verification also checks type membership and timestamp
  parseability. A v1 chain is rejected with an explicit "old chain
  format" error (never silently mis-verified), and appending to one
  is refused. The demo chain `data/chain.jsonl` was regenerated
  through the CLI's own seal/run flow: 10 records, all v2, verify
  ok=True, same verdicts (clean 0 flags, failures 5 flags) and the
  same 80.0% precision.
- **F2 (Medium) — precision consumed chains the verifier rejects.**
  `run` and `precision-demo` now verify the chain before producing
  any score; on failure they exit 1, name the failure on stderr, and
  print no score as valid. `run` also refuses to append to a chain
  that fails verification.
- **F3 (Medium) — decisions needed no real flag.** `compute_precision`
  validates every decision: `flag_id` required; when the flag list
  is supplied, the flag must have been emitted and the grader must
  match that flag's grader; duplicate decisions for one flag are
  rejected. Violations raise a ValueError naming every problem;
  invalid decisions are never counted. `run` validates the fixture
  decision set before appending any of it.
- **F4 (Medium) — missing spend became zero; negatives cancelled.**
  `capture.py` now requires `creditsUsed`/`tokensUsed` and validates
  them as non-negative finite numbers, in both `normalize_fetch` and
  `validate_run`. Missing or invalid spend rejects the capture with
  a named error; zero is never substituted for missing data. The
  supplied valid fixtures run unchanged.
- **F5 (Low) — incomplete seal envelopes verified.** `verify_seal`
  now requires a complete envelope: `sealed_at` present and
  parseable, `seal_algorithm` present and equal to the supported
  value; malformed envelopes return False.
- **F6 (Low) — precision output had no decision receipts.**
  Precision results carry per-decision receipts, and
  `render_precision` prints each: flag id, grader, decision, the
  chain seq it came from, and its note when present.
  `decisions_from_chain` now preserves seq and note.
- **F7 (Low) — stale task-pack owner in this file.** Session 2
  handoff item 4 above named Fable; it now names the Opus seat,
  with the correction noted inline at the line itself.

### Test receipts

- Before: **26 tests, 26 passed** (Session 1 suite, re-run at the
  start of this session).
- After: **49 tests, 49 passed** — the original 26 unchanged and
  passing, plus 23 new regression tests in
  `tests/test_audit_fixes.py`, named after the findings
  (test_f1_*, test_f2_*, test_f3_*, test_f4_*, test_f5_*,
  test_f6_*). No existing test was modified: none of the 26 pinned
  the buggy behavior.
- Harbor's scenarios, re-run by the builder against the fixed code:
  type-tamper → verify ok=False, first_bad_seq=10, exit 1;
  precision-demo refuses (exit 1, no score). Payload-tamper → same.
  Orphan decision via `run` → named ERROR, exit 1, no
  queue_decision records appended (was: 83.3%, exit 0). Missing
  spend → named ERROR, exit 1 (was: zero-cost score, 0 flags).
  Negative spend [100, −100] → named ERROR, exit 1. Incomplete seal
  envelope → verify_seal False; complete envelope still True.

### Law 2 state

Builder built, tested, and self-reviewed. **Independent
certification of the Session 1.1 fixes is OUTSTANDING** — it belongs
to a fresh auditor seat (Harbor's session audited the pre-fix code
and does not certify repairs to its own findings). Nothing here is
certified, shipped, or published.


## Session 2 candidate — 2026-10-28

Exact work request and original night hand-off are preserved in REQUEST.md and handoff/. Three Sol6.1Ultra builder lanes implemented claims, capture and CLI integration. Each tested and self-reviewed; the coordinator tested the combined CLI and live path. Independent review is a separate Sol6.1Ultra seat and is not replaced by builder receipts.

Packaging defect found at intake: the supplied ZIP contained21files but omitted fixtures/synthetic_firecrawl.json. The untouched49-test suite produced35FileNotFound errors. Its own10-record v2 chain verified and preserved both normalized runs, the card and five synthetic decisions. A loader-equivalent fixture reconstruction restores those values exactly; then all49baseline tests passed. Original fixture bytes remain unavailable. RESTORATION.md and baseline-recovery.json under receipts/ explain the recovery; the original data chain is unchanged.

Session2 end-to-end now extracts4claims from the original2answers, correctly reports all4uncited rather than inventing bindings, and stores populated claims before verdicts. The separate cited demonstration produces2SUPPORTED,2UNSUPPORTED,1CONTRADICTED; the false flag is killed in explicitly synthetic review data, giving66.7%claim-support demo precision. Synthetic judge import produces1separate JUDGE support and leaves the deterministic counts unchanged.

One actual keyless Firecrawl request completed2026-10-28T04:16:31Z,HTTP200,1807responsebytes,1provider-reported credit,tokens UNKNOWN. The claimed sentence matches the returned passage. Its3-record scored chain verifies; cost metering remains UNVERIFIABLE for missing token evidence. No paid account/key/fallback/retry was used; no autonomous agent generation was performed. Exact raw response, normalized fetch, CLI output and chain are preserved.

Builder self-review found and fixed a live metadata/chronology comparison gap before independent audit; reproduction and targeted tests are preserved. Current combined124tests pass on Python3.12.7 and Python3.9.6. See coordinator-python312-tests.log and lane receipts. Independent-audit status and final delivered hashes are reported in RESULTS.md; this progress entry does not self-certify the candidate. Queue UI, real Opus gold-pack validation and film remain later work.


### Consolidated independent-audit repair

The independent auditor found five issues after the initial green 124-test suite: citation attribution leaking to a following sentence, numerically equivalent decimal spellings treated as contradictions, factual headings omitted, source qualification markers erased, and non-finite numeric criteria accepted. The initial failure evidence and exact source hashes remain under receipts/audit/.

The claims builder repaired A1–A4 and added six regression methods. The coordinator repaired finite/non-boolean criteria validation for A5 and added five methods, including actual CLI refusal before chain writes. Both built, tested and self-reviewed; no auditor edited builder source. The final builder suite passes 135/135 on Python 3.12.7 and Python 3.9.6. The unchanged independent nine-method claim probes also pass for the builder. Independent closure is recorded separately in receipts/audit and RESULTS.md. No new network requests were made during remediation.


### Independent closure — final candidate

The separate Sol 6.1 Ultra auditor returned PASS for the bounded Session 2 candidate. All A1–A5 findings closed; 135/135 full-suite tests, 9/9 unchanged claim probes, 20 invalid numeric-criterion subcases and 18/18 valid CLI actions pass. The original NaN CLI now exits 1 with no score or chain. The helper verified 72 offline integrity checks and exact historical fixture reconstruction. Final source hashes, limitations and reviewer independence are recorded in receipts/audit/AUDIT-RECEIPT.json and CLOSURE.md. This closes the requested candidate build, not the later gold pack, queue UI or film.
