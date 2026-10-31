# Session 2 candidate receipt — 2026-10-28

Status: **PASS for the bounded Session 2 candidate after independent audit and repair.** All five material findings are independently closed. Built, tested and self-reviewed by the builders; independently reviewed by a separate Sol 6.1 Ultra seat that built none of the application.

Exact request: REQUEST.md. Original hand-off and full spec: handoff/. All 21 supplied files were read before dispatch. Three Sol 6.1 Ultra builder lanes handled claims, capture and integration; a separate Sol 6.1 Ultra seat audits the result.

## Results against the hand-off

| Part | Measured result | Receipt |
|---|---|---|
| Baseline | Untouched ZIP: 49 tests, 35 missing-file errors. Fixture recovered from its own verified chain: 49/49 PASS. | receipts/RESTORATION.md; baseline-recovery.json; baseline logs |
| Claims placeholder | Original two answers produce four claims before storage. All four are uncited and explicitly UNSUPPORTED. | receipts/lanes/integration-original-cli.log; integration-original-chain.jsonl |
| Claim verdicts | Cited data pack: 2 SUPPORTED, 2 UNSUPPORTED, 1 CONTRADICTED, with passages/offsets/hashes or explicit absence. | receipts/session2-demo-cli.log; session2-demo-chain.jsonl |
| Judge separation | One synthetic imported JUDGE support; deterministic 2/2/1 counts remain unchanged. No live model judge invoked. | receipts/session2-judge-demo-cli.log and chain |
| Planted grader error | Matcher misses monthly versus per month. Two invented confirmations give 100% demo precision; the invented kill lowers it to 66.7%. | tests/test_demo_pack.py; receipts/session2-demo-precision.log |
| Live capture | One real keyless Firecrawl POST: HTTP 200, 1,807 bytes, one reported free credit. | receipts/live-keyless-capture.json; live-summary.json |
| Live grading | One SUPPORTED claim; three chain records verify. Tokens UNKNOWN; cost truth UNVERIFIABLE. | receipts/live-scorecard.log; live-keyless-chain.jsonl |
| Pack interfaces | Original, cited, judge and saved-live files use data-only CLI interfaces. Future Opus gold pack remains unavailable. | TASK-PACK-FORMAT.md; fixtures/ |
| Builder verification | 135/135 tests on Python 3.12.7 and macOS Python 3.9.6. Original 49 tests unchanged. Independent final CLI closure passes all 18 valid actions. | receipts/audit/independent-closure-suite.log; final-python39-tests.log; audit/independent-closure-cli-commands.json |
| Independent audit | PASS after repairs; A1–A5 closed. 9/9 unchanged claim probes; 20 invalid criterion subcases rejected; 72 offline integrity checks pass. | receipts/audit/CLOSURE.md; AUDIT-RECEIPT.json |

## Real capture evidence

One request ran from 2026-10-28T04:16:31.650565Z to 04:16:31.981304Z. The fixed unauthenticated route is documented free by [Firecrawl rate limits](https://docs.firecrawl.dev/rate-limits#keyless-no-api-key) and [capabilities](https://docs.firecrawl.dev/capabilities). No Authorization header, retry or paid fallback was used. The returned document was a cached hit with its provider timestamp preserved. Provider tokens and agent-generation tokens are UNKNOWN, not zero.

Raw response: 1,807 bytes; SHA-256 `a71109267a1c99c98a2d5f0875aad0bacd286b7024b7bd2a5a660fed4249cfa3`.
Capture JSON SHA-256: `63edd1c8ee1555e474b39250a17f8d817166f52245daeb4674a92e4ad9d4cfac`.

This proves one real read and offline replay. It is not an autonomous agent run, capacity test, live judge trial or accuracy evaluation. The answer is explicitly caller-supplied. Mock transport evidence remains separately labeled synthetic.

## Independent findings and builder repair

The auditor found A1: trailing citation reused by a following uncited sentence; A2: numerically equal spellings labeled contradictory; A3: factual Markdown headings omitted; A4: source qualification markers removed before support matching; A5: non-finite numeric criteria accepted and able to suppress freshness flags. The independent failing tests, CLI reproductions, initial source hashes and findings remain under receipts/audit/.

The claims builder repaired A1–A4, added six regression methods, tested the real CLI, and self-reviewed. The coordinator repaired A5 with five regression methods including CLI refusal before chain mutation. Builder results: 38 claim tests, 9 unchanged independent claim probes, and 135 total tests pass on Python 3.12.7. Receipts are claims-repair-receipt.json and claims-repair-self-review.md under receipts/lanes/, plus numeric-criteria-builder-* under receipts/. The independent auditor reran the unchanged probes, numeric admission checks, full suite and actual CLI. All A1–A5 are closed; no material finding remains open. See receipts/audit/CLOSURE.md and AUDIT-RECEIPT.json. The reviewer built none of the application and made no source changes or network calls.

## Self-review and recovery

Every lane saved test logs, source hashes and self-review under receipts/lanes/. Coordinator self-review reproduced and repaired a live validation gap: normalized citations, judge decisions and timestamps now have to match the original capture plan. Five added regression tests pass, and the real capture remains byte-identical. See receipts/COORDINATOR-SELF-REVIEW.md and lanes/capture-provenance-before.json.

Original ZIP SHA-256: `a293743859b4811ed821afe522b75013b055d60de04c038b927b59d629407ede`. Its chain and original tests remain unchanged. The omitted fixture was recovered as identical normalized loader output; original raw fixture bytes were unavailable and are not claimed restored.

## Limits

Rule-based English prose extraction and exact/narrow scalar support are conservative. Tables, nested assertions, pronouns, multilingual text and broader entailment need review. UNSUPPORTED means no support identified by these checks. Imported judge identity is declared provenance; matching a passage does not certify judge correctness. No actual judge-seat trial occurred.

Historical cost per present task element is labeled separately from supported-claim cost. Missing metering and zero denominators remain unavailable. Chain hashes prove stored-byte consistency, not authenticated source truth or multiwriter safety.

Queue UI, real Opus gold-pack validation, autonomous agent loop, film and hosting remain later work. No publication, outreach, external upload, purchase or pay-as-you-go call occurred. Questions for Stephen: none.

## Delivery

Final local ZIP: `Scoring-Layer-Session2-Candidate-2026-10-28.zip`. Contents: source, tests, data packs, original hand-off/spec and builder/independent receipts, with a manifest. Caches, credentials, temporary extraction files and intermediate backup ZIPs are excluded. Package size, SHA-256 and extracted-package checks accompany delivery. Local delivery honors the hand-off restriction: nothing published or sent.
