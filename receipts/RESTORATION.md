# Restoration before changes

The first checkpoint checked was Stephen’s attached Session 1.1 ZIP, SHA-256 `a293743859b4811ed821afe522b75013b055d60de04c038b927b59d629407ede`. The archive includes the full source and a ten-record v2 evidence chain, but no `fixtures/` directory. The untouched package runs 49 tests with 35 missing-file errors; see `baseline-as-delivered-tests.log`.

A targeted filename search in `/Users/carrie/my-project`, `/Users/carrie/Documents`, and `/Users/carrie/.local/bin` found no `synthetic_firecrawl.json` before recovery. No original raw fixture bytes were available in the provided checkpoint. The included `data/chain.jsonl` verified all ten records and held the normalized task, two runs and five synthetic review decisions. Those were recoverable without altering scorer code.

Recovered `fixtures/synthetic_firecrawl.json` by wrapping those normalized fetches in the existing loader’s Firecrawl-shaped input format. The wrapper’s `response.success: true` is reconstructed metadata, ignored by the historical loader, and is not a claim about a real API request. The resulting loader output, including both final answers and their empty claims, equals the recorded runs exactly. The task card and decisions also equal their recorded originals. This is a loader-equivalent reconstruction, not an original-byte restoration. The preserved original ZIP and chain remain unchanged.

Before Session 2 code edits, all 49 baseline tests passed. `baseline-recovery.json` carries hashes, equality checks and chain verification; `baseline-restored-tests.log` is the raw test output. Restoration was used for the missing data; speculative core patchwork was unnecessary.

Source archive inventory: 21 files, all read before builder dispatch. No independent certification was inferred from these builder checks.
