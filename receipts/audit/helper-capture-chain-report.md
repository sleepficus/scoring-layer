# Independent capture / evidence-chain audit helper

Checker: `/root/independent_audit/capture_chain_check`; builder of none of the audited code. Parent `/root/independent_audit` owns the combined audit. Read REQUEST.md, full handoff/spec, BUILD-SHEET.md, PROGRESS.md and FOR-CREW. Questions for Stephen: none.

Bounded result: **72/72 offline admission/integrity checks pass**, with one malformed-criterion finding below. No network, paid API or new capture was invoked. Original source, historical chain and genuine live capture hashes remained unchanged. Writes are only helper reports/probes beneath `receipts/audit/`.

## H-CAP-1 — medium; pre-existing criterion-validation gap

`scoring/sealing.py:46` and `:75` admit `freshness_bound_hours: NaN` because numeric NaN does not compare `<= 0`. Python's JSON parser accepts that token, the canonical serializer hashes it, and the CLI verifies the resulting seal. The freshness grader then compares `age_hours > NaN`, always false. A malformed data pack can silence the stale-cache criterion instead of being rejected.

Measured CLI result: `run --session1 --pack receipts/audit/helper-invalid-bound-repro.json --chain NEW_PATH` exits **0**, the seal verifies, and the known seven-hour stale failure fixture emits **0 freshness flags** (valid original: one). Other flags remain visible. Not observed in valid supplied live/demo packs. No paid route or actual spending involved. `NaN` is outside RFC JSON; this finding concerns the parser's actual admitted input and the promise of a positive bound. `sealing.py` is unchanged from supplied Session 1.1, so this is not a Session 2 regression.

Receipts: runnable `helper-capture-chain-probe.py`, exact malformed fixture `helper-invalid-bound-repro.json`, CLI output `helper-invalid-bound-cli.log`, measured values/code hashes `helper-capture-chain-results.json`. Proportional repair: reject non-finite freshness criteria before sealing, including question overrides, with one targeted admission regression.

## Passing scope

- Genuine stored capture validates offline: SHA `63edd1c8ee1555e474b39250a17f8d817166f52245daeb4674a92e4ad9d4cfac`; one non-synthetic urllib HTTP200 receipt for `https://example.com/`, 1,807 exact response bytes. Fixed unauthenticated `/v2/scrape` request, markdown/main-content only. Provider reports one credit; tokens stay UNKNOWN and trigger cost UNVERIFIABLE, not zero/pass.
- Altered body hash/size, normalized markdown/spend, missing UNKNOWN status, injected Authorization/endpoint/paid fallback/retries, omitted receipts, changed answer/citations/judge decisions, altered run/seal start, out-of-bounds response time, changed task criteria, incomplete/error/blocked packets and inconsistent synthetic labels are refused. Invalid provider spend fails even with recomputed byte checksums. CLI rejects blocked/tampered packets before score or chain creation.
- Static transport review: no API-key read, authorization, cookies, ambient proxy, redirect following, retries or paid fallback. Request-attempt/pre-seal packet is flushed/fsynced before transport. Failures preserve receipts and stop. Receipt hashing establishes internal byte consistency, not authenticated network provenance of arbitrary untrusted files; code/docs state that limit.
- Session 1.1 F1: ten-record original v2 chain verifies; copied type/time/payload/seq tampering and old-format admission/append fail. F2: score/precision refuse those chains without score or append. F3: five real decisions validate at 80%; orphan/duplicate/missing/wrong-grader fail; orphan CLI creates no chain. F4: missing/negative/non-finite/boolean spend fails. F5: complete envelope verifies; missing metadata/card edits fail. F6: all decision IDs/seqs/notes appear beneath precision. F7: PROGRESS handoff names Opus.

## Historical fixture recovery

Independently imported untouched original `capture.py` and loaded the reconstructed fixture. Source/chain equal ZIP entries byte-for-byte; ZIP has no fixture entry. ZIP SHA `a293743859b4811ed821afe522b75013b055d60de04c038b927b59d629407ede`; chain SHA `a4be29b831c6b1d4302b319c9623476491290b528ca68543a933367098a6fa4a`, equal to workspace original.

Original loader yields **exact equality** for task card, both normalized runs and five review decisions. Recovered fixture SHA `5a347fbd509b92c1ef76ec25c5c4e36e3011d35e56ddddd3b3c06f73dc005076`. Current loader differs only in the expected Session 2 `claims_note`. Loader-equivalent reconstruction is substantiated; original raw fixture bytes remain unavailable. Full receipt: `helper-historical-fixture-equality.json`.

Runtime Python 3.12.7. Parent owns full-suite and normal CLI reruns; this helper does not claim those. Raw passing results and failing acceptance output are preserved before any builder repairs.
