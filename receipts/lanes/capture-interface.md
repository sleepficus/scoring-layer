# Capture lane — builder receipt

Built, tested and self-reviewed by `/root/capture`, Sol 6.1 Ultra.
Independent review remains with a different seat. No real Firecrawl request
was sent by this lane; the coordinator owns that one live invocation.

Read first: REQUEST.md, handoff/HANDOFF.md, the complete supplied spec,
BUILD-SHEET.md and PROGRESS.md. The supplied snapshot and its original
capture.py were preserved by the coordinator before this extension. This
lane did not repair or replace the historical chain.

## Callable and data contract

`scoring.live.capture_live_task_pack(pack_path, output_path, timeout=45)`
returns and persists a capture packet. The output path must be new. The CLI
surface is `python3 -m scoring.cli capture-live --pack PLAN --output NEW_FILE`.
Then `python3 -m scoring.cli run --pack NEW_FILE --chain NEW_CHAIN` loads the
same run-record keys as the fixtures through `capture.load_task_pack`.

The input is ordinary JSON: `task_card`, `run_id`, `agent_label`,
`final_answer`, and `fetches` containing `url`, `question_ids`, `relied_on`.
Optional `citations`, `judge_decisions` and `notes` are data. The card is sealed
and the input plan hashed before the first request. This harness reads pages;
the answer is explicitly labeled caller-supplied. It performs no agent answer
generation and claims no measured answer-generation token count.

The only network destination is `https://api.firecrawl.dev/v2/scrape`, with
fixed markdown-only options. No credentials, ambient API keys, cookie store,
proxy configuration, API redirects, automatic retries, account changes or paid
fallback are used. Supplying `api_key` is refused before network access.
HTTP 402 or 429 records BLOCKED and stops. Other transport/provider failures
record INCOMPLETE. Neither status can be loaded for scoring.

Request bodies, timestamps and hashes are durable before sending. Received
bytes are stored exactly as base64 with size and SHA-256. Normalized fetches
must equal those bytes on reload. Unknown provider spend/cache values remain
None/UNKNOWN; missing spend is never silently zero. Provider-reported scrape
tokens, if present, have their own scope. They do not measure the agent's
answer-generation tokens. The original synthetic fixture loader still rejects
absent, negative or non-finite spend.

Injected test transports are marked SYNTHETIC_TEST_TRANSPORT and synthetic
through the packet/run/scorecard. A test body cannot silently serve as live
proof. Receipt hashes establish stored-byte consistency, not source
truthfulness or unforgeable network provenance.

## Measured checks and self-review

- 29/29 targeted capture tests pass. See capture-tests.log. This includes five
  new test methods for attribution/time provenance after the coordinator
  found the focused gaps described below.
- 124/124 tests passed in this lane's full suite run. See
  capture-regression-suite.log. The coordinator owns the final complete rerun.
- CLI mock surface: capture-live, run, verify and precision-demo each exit 0;
  3 chain records verify; the run stores 1 exact HTTP receipt and 1 claim.
  See capture-cli-mock.log, explicitly synthetic with no network requests.
- Reviewed source and actual CLI output. Checked duplicate-output refusal
  before another request, no Authorization despite an ambient test key,
  malformed and missing provider data, 403-as-document preservation, limit
  stops, raw body tampering and normalized-content tampering. Self-review found
  and fixed missing durable attempted-call evidence on a timeout; the
  regression now asserts a TRANSPORT_ERROR receipt with unknown response/spend.

File hashes, runtime and log hashes are in capture-receipt.json.
Questions for Stephen: none. A service rejection, network failure or free IP
limit on the coordinator's real invocation must be reported as observed.

## Current official source checks — 2026-10-28

[Rate limits](https://docs.firecrawl.dev/rate-limits#keyless-no-api-key) describes
free keyless access with daily IP request/credit caps and HTTP 429 at a cap.
[Capabilities](https://docs.firecrawl.dev/capabilities) explicitly lists
`/v2/scrape` as accepting no API key.
[Billing](https://raw.githubusercontent.com/firecrawl/firecrawl-docs/main/billing.mdx)
distinguishes free requests from paid-plan pay-as-you-go. These records support
the fixed unauthenticated route; no inference about a private account plan was
needed or made.

[Scrape API](https://docs.firecrawl.dev/api-reference/endpoint/scrape) documents
the request/response shape and error responses. Its displayed basic response
does not guarantee the fixture's cost/cache fields. The capture therefore
preserves missing fields explicitly instead of manufacturing those receipts.

## Focused provenance follow-up — 2026-10-28

The coordinator found two consistency gaps during builder self-review:
normalized citations/judge decisions could differ from the original captured
plan, and the run start could differ from the capture/card-seal start.
The synthetic reproduction accepted changed/omitted citations, added judge
rows and a changed run start before repair. These failures are preserved in
capture-provenance-before.json, with the pre-repair source ZIP and its hash.
Restoring the supplied Session 1 snapshot was ruled out because it predates
live capture; the focused Session 2 source was preserved before editing.

The validator now requires citations and judge decisions to match both the
presence and content of the original plan. An omitted value is distinct from
an explicit null/empty value. The run start and card seal time must equal the
original capture start. All capture/receipt times must be aware ISO timestamps
with the observed request/response ordering inside the capture interval.
Five new regression test methods cover changes, additions, omissions, invalid
clock values and out-of-interval response times. The 29 capture tests and
124 combined tests pass after repair. The existing real capture supplied by
the coordinator also validates, with its file SHA unchanged; no request was
sent or retried. Exact current file/log hashes are in capture-receipt.json.
