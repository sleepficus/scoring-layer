# Independent audit — initial findings

Reviewer: `/root/independent_audit`, GPT-6.1 Sol Ultra. This seat did not build or modify any candidate source or builder tests. A fresh helper seat reviews capture/chain separately. No network requests or paid routes are used by this audit.

Initial candidate verdict: **REPAIR REQUIRED**. The ordinary suite passes, but four independent claim probes expose incorrect verdict/admission behavior. All can be reproduced without a provider call and repaired in a focused claims-module pass. Exact source hashes are in `initial-source-hashes.json`.

## A1 — Citation after one sentence also binds the following uncited sentence (High)

At `scoring/claims.py` lines 149–168, a trailing reference is attached to the preceding sentence without being consumed from the next sentence’s span. Input `WidgetForge Pro costs $49 per month. [1] WidgetForge Pro includes 1200 requests per month.` gives both claims citation `[1]`. When the fetched page contains both facts, both are SUPPORTED even though the reference belongs to the preceding sentence. This violates claim-specific citation binding and can inflate the supported-claim denominator. I independently reproduced it through both the module and the real CLI, which exited 0 with two supported claims.

Receipt: `claim_adversarial_probes.py::test_a1_postsentence_reference_does_not_bind_following_uncited_sentence`; `citation-leak-cli-before.log`; `claims-observations-before.json`. Required outcome: the first claim can bind the trailing reference; the following uncited sentence must remain uncited/UNSUPPORTED unless it has its own citation.

## A2 — Numerically equal decimal spellings are labeled CONTRADICTED (Medium)

The scalar extractor at lines 254–259 stores numeric strings after only comma removal, and the contradiction branch at line 309 compares those strings. `$49` versus `$49.00`, `$49.0` versus `$49`, and `$1200` versus `$1,200.00` produce CONTRADICTED despite identical values and identical subject/relation/unit context. This is ordinary price formatting, not unresolved paraphrase semantics.

Receipt: `test_a2_equal_decimal_price_is_not_contradiction`; three failing subcases in `claim-adversarial-before.log`. Required outcome: compare supported narrow scalar values numerically with exact decimal semantics, retaining the original source spellings as evidence. Truly unequal values must still contradict.

## A3 — A factual Markdown heading is silently excluded from all claim counts (Medium)

At line 158, every segment starting with `#` is skipped. `# WidgetForge Pro costs $49 per month [1]` produces zero measured claims and no row declaring absence or uncertainty. A straightforward factual assertion should not disappear because it is a heading. The broader declared limits on tables/nested/multilingual parsing do not justify silently dropping this basic assertion.

Receipt: `test_a3_factual_markdown_heading_is_measured`. Required outcome: extract the factual heading while preserving its exact answer span, or explicitly record its ungraded status; do not report zero claims as complete coverage. Ordinary nonfactual headings need not become factual claims.

## A4 — Source qualification markers are discarded before deterministic support (High)

The shared `_clean` at lines 44–49 drops any numeric square-bracket text and all asterisks from source passages. A source `WidgetForge Pro costs $49 per month.*` followed by `*Only if billed annually.` becomes exact unqualified support. `WidgetForge Pro costs $49 per month [2024].` also becomes exact unqualified support. The code is erasing source meaning before deciding whether the claim is supported. This is distinct from a false flag exposed in the planted demo: it creates false supported claims.

Receipt: `test_a4_source_qualification_markers_are_not_erased_into_support`; two failing subcases in `claim-adversarial-before.log`. Required outcome: preserve source qualification/reference markers or send unresolved note context to semantic residue with explicit reason/receipts. Conservative UNSUPPORTED with `needs_judge` is acceptable; do not assert deterministic support by deleting the qualification.

## Independently passing checks so far

- Python 3.12.7 full suite: **124/124 pass**, exit 0, `independent-suite.log`.
- Fifteen actual CLI actions: run, verify, precision for original, cited demo, synthetic judge demo, saved genuine live capture, historical Session 1. All exit 0; commands and logs in `independent-cli-commands.json` and `cli-*.log`.
- The original fixture yields four uncited UNSUPPORTED claims with missing bindings declared. The cited demo yields 2 SUPPORTED, 2 UNSUPPORTED, 1 CONTRADICTED; the synthetic kill gives 66.7% precision. The JUDGE example retains the deterministic ledger and adds one separate judge support. Historical replay retains 0/5 flags and 80% demo precision.
- Offline genuine-capture replay yields one supported source passage and a cost UNVERIFIABLE flag because token metering is absent; three records verify. This audit does not independently prove the historical network event from first principles, and makes no new request. It checks the stored evidence and the coordinator’s recorded transport provenance.

The independent probe file contains nine methods: five controls pass and four methods fail (seven failing subcases). These failures are saved before remediation. Capture/chain helper findings will be appended to this same batch; no source has been changed by the audit.

Questions for Stephen: none. No broad redesign is requested; repair the four narrow behaviors, have the builder test/self-review, then this seat will perform targeted closure and one final suite/CLI replay.

## A5 — Non-finite sealed criteria can disable a deterministic bound (Medium)

The independent capture/chain helper found that `sealing.validate_card` accepts a NaN freshness bound. Python’s JSON loader admits the NaN token, the card is sealed, the CLI exits 0 and the known seven-hour stale fixture no longer fires its freshness flag because `age > NaN` is false. This is inherited input-validation behavior and is directly relevant to the sealed-criteria guarantee. Finite, non-boolean numeric validation is needed for card/question freshness and cost bounds before writes; ordinary valid task cards should remain unchanged.

Receipt: `helper-invalid-bound-repro.json`, `helper-invalid-bound-cli.log`, and `helper-capture-chain-probe.py`. Helper independently reports 72/72 bounded offline live-receipt/chain/precision/fix checks passing; full receipt is `helper-capture-chain-results.json`. Exact historical-loader reconstruction comparison is being finalized. This completes the consolidated material findings batch: A1–A5.
