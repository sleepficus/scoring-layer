# Scoring Layer — Session 2 candidate

A standard-library Python CLI that binds research-answer claims to passages in the pages actually captured. Each claim records SUPPORTED, UNSUPPORTED or CONTRADICTED with source text and offsets, or an explicit absence. Rule-based deterministic results and imported JUDGE results remain separate. No composite score is produced.

This is the Session 2 candidate requested in `REQUEST.md` and `handoff/HANDOFF.md`. Independent review and measured results are in `RESULTS.md` and `receipts/`. The source ZIP omitted its synthetic fixture; `receipts/RESTORATION.md` records its exact normalized-data recovery from the supplied chain.

## Run the CLI

No dependency installation is needed. Python 3.12 is the build-sheet target. The final test and independent review counts are recorded in RESULTS.md. Python 3.12.7 and macOS Python 3.9.6 were exercised. From this folder:

```sh
python3 -m unittest discover -s tests -v
work=$(mktemp -d)
python3 -m scoring.cli run --pack fixtures/session2_claim_support.json --chain "$work/demo.jsonl"
python3 -m scoring.cli verify --chain "$work/demo.jsonl"
python3 -m scoring.cli precision-demo --session2 --chain "$work/demo.jsonl"
python3 -m scoring.cli run --pack fixtures/session2_judge_demo.json --chain "$work/judge.jsonl"
```

The first demo contains five factual candidates: two supported, one contradicted, and two unresolved by deterministic checks. The planted false flag is `monthly` versus `per month`. The explicitly synthetic review decisions confirm two flags and kill that false flag, moving demo precision from 100% to 66.7%. This is a demonstration of the accounting, not a measured real-world accuracy rate. The second file imports a separately labeled synthetic judge decision; deterministic results stay unchanged.

To exercise the restored original answers, use `--pack fixtures/synthetic_firecrawl.json`. Those answers contain no citations: Session 2 reports their four claims unsupported and declares the missing bindings. `--session1` selects the historical four-grader replay, which preserves its original 0/5 flag counts and 80% synthetic review precision. The original `data/chain.jsonl` remains byte-for-byte unchanged. Use a new chain path for each replay; duplicate run IDs are refused.

## Real free capture

One real keyless capture is preserved at `receipts/live-keyless-capture.json`. It can be scored offline with a new chain path. The real response reports one credit, omits token usage, and supports the caller-supplied probe sentence. The cost dimension therefore flags token metering UNVERIFIABLE rather than inventing zero.

A new capture is an explicit network operation:

```sh
python3 -m scoring.cli capture-live --pack fixtures/live_keyless_example_plan.json --output "$work/capture.json"
python3 -m scoring.cli run --pack "$work/capture.json" --chain "$work/live.jsonl"
```

The sample plan shows the file format; choose an appropriate public research target for a new task. This candidate only uses Firecrawl’s documented keyless free scrape route. It sends no API key, never purchases credits, never falls back to paid access, and does not retry. HTTP 402/429 records a blocked capture. Every request is recorded before it is sent; each response is preserved byte-for-byte. A new output filename is required. The capture harness reads pages; it does not autonomously generate the answer or call a model.

## Data-only task packs

See `TASK-PACK-FORMAT.md` for synthetic fixtures, live plans, citation metadata and judge import. The future Opus gold pack is not included and is not represented as validated. It can supply data through these interfaces without core changes.

## Limits

Claim extraction is conservative English prose parsing; it does not guarantee every atomic claim in tables, nested assertions, pronouns or multilingual text. Exact complete statements and narrow scalar assertions are deterministic; paraphrases can need a judge. UNSUPPORTED means no support identified by this check, not proof that no passage entails the claim. External judge receipts are checked against actual captured text; semantic judge correctness is not authenticated by matching a hash. Imported judge identity is declared provenance, not cryptographic identity verification.

Credits, scrape tokens, answer-generation tokens and judge cost are distinct. Missing metering stays UNKNOWN. Hashes detect changed stored bytes under the recorded chain; they are not a signature proving who fetched or judged a source. The queue UI, autonomous research-agent loop, real gold-pack validation, hosting and film are later work. Nothing was published or sent externally.
