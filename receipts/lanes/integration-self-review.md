# Integration builder lap — Session 2

Exact request read: `REQUEST.md`, `handoff/HANDOFF.md`, full supplied spec,
`BUILD-SHEET.md`, and `PROGRESS.md`. Questions for Stephen: none.

Before editing, parent recovered the omitted fixture from the original verified
10-record chain and measured the untouched restored baseline at 49/49 tests.
The attached ZIP remains unchanged. Recovery receipt: `receipts/baseline-recovery.json`.

## Built behavior

- Historical `grade_run` remains the four-grader Session 1 replay. CLI `run`
  now uses `grade_session2_run`; `--session1` names the historical path.
- The exact final answer is re-extracted before run storage. Original supplied
  answers have no citations, so their four extracted claims receive UNSUPPORTED
  with explicit absence. No citations were invented to make the old clean run pass.
- The claim ledger and scorecard retain exact answer spans, document passages,
  offsets, hashes, citation binding errors or explicit absence, and card seal.
- All runs, judge rows, review decisions, ID collisions, and seals are checked
  before a task card, run, verdict, or decision is appended. Invalid input prints
  no scorecard. Repeated run IDs cannot reuse decision/flag identities.
- Live packets use the capture lane's validation. Original request/response
  receipts are carried into the chain inside `run.capture_evidence`, preserving
  the raw response behind each normalized fetch's receipt_index.
- DETERMINISTIC and JUDGE support counts, cost denominators, and review precision
  are separate. JUDGE never upgrades the deterministic count. Historical cost
  arithmetic is labeled as present required elements, not supported answer claims.
- Missing live metering is UNKNOWN; cost verification becomes UNVERIFIABLE.
  No missing unit becomes zero. Ratios with missing spend or zero supported
  claims are unavailable. Answer-generation and separate judge-seat tokens/cost
  are explicitly unmeasured.

## Tests and actual user surface

`integration-tests.log`: 12/12 targeted tests. They test the original fixture,
a separate data-only pack, passage injection rejection, pre-write refusal,
duplicate IDs, changed criteria, separate JUDGE counts/precision, strict
historical replay, UNKNOWN cost, and injected transport capture → CLI → chain.

Actual subprocess commands, each exit 0, are saved as `integration-original-cli.log`,
`integration-original-verify.log`, `integration-original-precision.log`, and
`integration-legacy-cli.log`. I read the complete original CLI output and its
precision/verification output after execution. Original Session 2 output:
2/7 deterministic flags for clean/failure runs, four uncited claims, four claim
flags pending review; 10-record chain verifies. Explicit Session 1 remains 0/5
flags and 80% demonstration precision.

## Self-review corrections

I traced input → normalization → extraction → verdict → chain → rendered output.
I corrected two issues found during that review: raw live receipts initially
would have stayed only in the capture file, and standalone precision output
could have omitted the synthetic label or blended JUDGE into legacy formatting.
Raw receipts now travel into the chain; stored Session 2 verdicts force method
separation even without an explicit precision option; synthetic chain precision
keeps its fixture label.

## Limits and audit state

This is a candidate, built/tested/self-reviewed by the integration builder.
Independent audit is pending and is not certified by this receipt. This lane
made zero network calls. Real Firecrawl access/run belongs to the capture lane
and coordinator. Rule-based extraction/entailment coverage remains bounded as
printed in the scorecard. Queue UI, film, real Opus gold pack and external
publication are outside this slice. The code cannot authenticate a forged local
receipt as Internet truth; capture provenance must be inspected alongside it.
