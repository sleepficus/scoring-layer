# Independent audit closure — Session 2 candidate

**Verdict: PASS for the bounded Session 2 candidate after A1–A5 repairs.** No material finding from this consolidated audit remains open. This is an independent candidate review, not a claim of production accuracy or completion of the later gold-pack/UI/film work.

Reviewer: `/root/independent_audit`, GPT-6.1 Sol Ultra. This seat built none of the audited application and changed no builder source or tests. `/root/independent_audit/capture_chain_check` independently checked the capture/evidence subset and is finished/stopped. Root and `/root/claims` implemented, tested and self-reviewed their repairs before this closure. Exact final source/test hashes are in `final-source-hashes.json`; the initial snapshot and failing evidence remain intact.

## Measured closure

| Check | Independent result | Receipt |
|---|---|---|
| Full finished-candidate suite, Python 3.12.7 | 135 tests, 135 pass, exit 0 | `independent-closure-suite.log` |
| Original unchanged adversarial claim probes | 9 methods pass, exit 0; original 4 failing methods are closed | `claim-adversarial-closure.log`, `claim_adversarial_probes.py` |
| Finite criteria admission | 20 invalid-value/location subcases rejected; actual NaN CLI refuses before score/chain; 2 methods pass | `criteria-adversarial-closure.log`, `criteria_adversarial_probes.py` |
| Actual CLI on original/demo/judge/saved-live/legacy/A1 reproduction | 18 run/verify/precision actions, all exit 0 | `independent-closure-cli-commands.json`, `closure-cli-*.log` |
| Exact original A5 malformed fixture | exit 1; no chain created; no score printed | `closure-cli-a5-invalid.log` |
| Capture/chain/precision historical fixes and provenance | 72 bounded offline checks pass; source-dependent criterion finding separately closed above | `helper-capture-chain-results.json`, `helper-capture-chain-report.md` |
| Historical fixture recovery | Original ZIP loader yields exact task, both normalized runs and all five decisions; original chain unchanged | `helper-historical-fixture-equality.json` |

## Finding closure

- **A1 citation leakage — closed.** Post-sentence `[1]` is consumed only for the preceding sentence. The exact former CLI reproduction now reports one supported first claim and one uncited unsupported second claim. An independently retained raw claim span still equals the final-answer slice.
- **A2 decimal equality — closed.** Narrow values use Decimal equality; `$49`, `$49.0` and `$49.00`, including comma variants, support rather than contradict. The truly different-value control still contradicts. Original passage spellings remain in receipts.
- **A3 factual heading omission — closed.** An ordinary factual Markdown heading produces a measured claim; nonfactual headings remain labels. Exact answer spans are retained.
- **A4 discarded source qualifications — closed.** Numeric square-bracket qualifiers and footnote markers remain source evidence. Both original qualification probes now yield semantic residue rather than unsupported erasure into SUPPORTED. Exact qualification passages are exposed. The source review confirms answer-citation cleanup is separate from source normalization.
- **A5 non-finite criteria — closed.** Card/question freshness and both cost units reject NaN, infinities and booleans before sealing/writing. The exact original malformed fixture now exits 1 without a score or chain. Finite valid criteria and existing seals continue through the full suite and CLI replay.

Initial `FINDINGS.md`, `claim-adversarial-before.log`, the false-attribution CLI output and the NaN acceptance log are preserved. This closure does not rewrite the original failed result.

## End-to-end outcome against the hand-off

The restored original two answers now store four extracted claims, with every missing citation declared; no inferred sources are added. The separate five-claim data pack gives 2 SUPPORTED, 2 UNSUPPORTED and 1 CONTRADICTED with passages or explicit absence. The planted `monthly`/`per month` miss remains visible: the invented kill decision produces 66.7% synthetic claim-support precision. This is a demonstration of precision accounting, not real-world accuracy evidence. A data-only judge import adds one separately labeled JUDGE support and leaves all deterministic counts unchanged. Historical Session 1 replay retains the original 0/5 flags and 80% synthetic precision.

The saved genuine live packet validates offline, its exact response is 1,807 bytes, HTTP200, one reported credit, missing token usage UNKNOWN. The actual CLI replay produces one supported passage and one cost UNVERIFIABLE flag, with a three-record verified chain and the raw HTTP receipt retained in the run. The original historical chain SHA remains `a4be29b831c6b1d4302b319c9623476491290b528ca68543a933367098a6fa4a`; the genuine capture SHA remains `63edd1c8ee1555e474b39250a17f8d817166f52245daeb4674a92e4ad9d4cfac`.

## Limits that remain explicit

The claim extractor and deterministic entailment are conservative rules, not a guarantee of exhaustive atomic fact extraction from arbitrary tables, languages or nested prose. Unresolved paraphrases and source notes require semantic review. Imported judge provenance is declared data and its text is checked against captured sources; neither matching hashes nor this audit prove the judge’s semantic correctness or identity. The preserved live packet is internally consistent evidence of the coordinator’s recorded request; this offline audit does not independently reconstruct the historical network event and made no new request. Credits, provider scrape tokens, answer-generation tokens and judge cost retain separate scopes; omitted metering never becomes zero.

The future Opus gold task pack is absent and unvalidated; the interfaces accept data-only packs, but arbitrary future packs have not been tested. Queue UI, autonomous agent generation, film, hosting and external publication are later work. Source hashes must remain the audited hashes when packaged; any later application change needs proportionate verification. Questions for Stephen: none.
