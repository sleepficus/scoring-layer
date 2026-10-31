# BUILD REPORT — Scoring Layer E1 repair (builder seat)

**Builder:** Muse builder lane, 2026-10-28. **Status: built, tested, self-reviewed — NOT certified.** Certification is a separate seat (Law 2); nothing in this report claims it.

**Input package:** `scoring-e1-fix-handoff-ALL-IN-ONE-2026-10-28.zip`, SHA-256 verified on receipt: `0096484b0b2542d5fc2cc6a73c6eccada3f2d363811c2e5242e2e1328cbb287b` ✓. Built on the enclosed certified candidate tree exactly as handed off.

## The defect (external audit finding E1, LOW)

Punctuation adjacent to a citation token survived claim normalization in `scoring/claims.py`, so the narrow assertion matcher failed on otherwise exact support: `Acme Pro includes 500 requests [1], and …` normalized to `"Acme Pro includes 500 requests ,"` → UNSUPPORTED; `([1])` left `"()"` residue with the same result. Fail-closed (support understated, never invented), but a correctness defect in a common prose shape.

## What changed

**One source file modified: `scoring/claims.py`** (SHA-256 `2dee6776…a2656` → `c3e0c974…607f`). All changes are inside claim-side normalization; passage normalization (`_clean`/`_norm`) is untouched, and non-removable references are returned byte-verbatim, hugging punctuation included.

1. `claims.py:31-35` — new `_REF_HUG` pattern: a *removable* citation token plus an optional hugging comma (`\s*,` not followed by a digit). Digit-grouping commas (`,200`) can never be consumed.
2. `claims.py:63` — `_clean_claim` substitutes via `_REF_HUG` with the original removability predicate unchanged, so a removed citation takes its hugging comma with it.
3. `claims.py:67-70` — empty parentheses left by a removed citation (`([1])` → `()`) are removed. Non-empty parentheses are content (e.g. a `(per month)` unit context) and are never touched — pinned by a guard test.
4. `claims.py:71-74` — a comma orphaned at the end of the cleaned claim (e.g. `([1]),`) is stripped as a separator remnant. Claim-side only.

**One file added: `tests/test_e1_regression.py`** (11 tests, named for the finding). The certified tree's 135 tests are byte-unmodified. `MANIFEST.json` / `SHA256SUMS.txt` were deliberately **left as the certified baseline's record** — they no longer describe `scoring/claims.py` or the added test file, by design; `REPAIR-SHA256SUMS.txt` (this tree, `sha256sum -c` verifiable) is the repair candidate's manifest.

Tree diff vs. the certified candidate (verified with `diff -rq`): `scoring/claims.py` modified, `tests/test_e1_regression.py` added, this report and `REPAIR-SHA256SUMS.txt` added. Nothing else.

## Measured results

| Check | Before (certified tree) | After (this tree) |
|---|---|---|
| Full suite (`python3 -m unittest discover -s tests`) | 135 tests, OK | **146 tests, OK** (135 + 11 new) |
| E1 regression tests on **pristine** code | **9 FAIL**, 2 ok — the 2 passes are the designed control + guard, which must pass on both versions | — |
| E1 regression tests on fixed code | — | **11/11 OK** |
| Demo: `session2_claim_support` run + verify | 6 records, ok=True; verdicts 2 SUPPORTED / 1 CONTRADICTED / 2 UNSUPPORTED | run log byte-identical; verdicts identical; ok=True |
| Demo: `session2_judge_demo` run | verdicts incl. JUDGE SUPPORTED row | byte-identical |
| Demo: `synthetic_firecrawl` run + precision-demo | OVERALL **80.0%** (4 confirmed, 1 killed, 4 pending) | precision log identical — **80.0%** |
| Demo: precision-demo `--session2` | claim-support 66.7%, OVERALL 66.7% | identical |

**CLI-surface E1 check** (the surface the fix is used at, not only unit calls): a pack cloned from the demo fixture with the two supported facts rewritten in E1 shapes (`…$49 per month [1], and includes…` and `…([2])`), graded via `scoring.cli run` on both codebases — pristine: claims graded UNSUPPORTED / SUPPORTED / UNSUPPORTED; fixed: **SUPPORTED / SUPPORTED / SUPPORTED**, sealed into a verifiable chain.

## Adversarial re-attack (audit's probe shapes, both codebases)

Wrong-subject passage, partial passage, 403 citation, unresolved reference, qualified passage (`[…]` marker retained), bracketed prose `[only if paid annually]` retained: **UNSUPPORTED on both versions** — the fail-closed direction is intact; nothing was loosened into support except verbatim/full-assertion equality.

Three verdict movements beyond the audited scalar shapes, all disclosed for the certifying seat:

1. **Negated exact statement** (`Acme Pro does not include 500 requests [1],` vs. the identical passage): UNSUPPORTED → **SUPPORTED**, via complete-statement equality with the negation retained verbatim on both sides. Pre-fix failure was the comma residue alone; this is the E1 mechanism on the exact-statement path.
2. **Qualified exact statement** (`includes up to 500 requests [1],` vs. identical passage): UNSUPPORTED → **SUPPORTED**, same path, qualifier retained verbatim on both sides.
3. **Different value, comma shape** (`includes 900 requests [1],` vs. passage's 500): UNSUPPORTED → **CONTRADICTED**. The repaired normalization lets the contradiction branch see the assertion. It never routes through SUPPORTED.

Also checked: a passage that itself ends in a comma (newline-truncated list line) grades UNSUPPORTED on both versions — no movement. One internal side effect, demo-verified harmless: clause-boundary detection in extraction calls the same `_clean_claim`, so a clause whose verb was masked by citation punctuation can now be seen as a boundary; the full demo battery's claim sets and verdicts are unchanged.

## E3 — skipped, deliberately

E3 (INFORMATIONAL: label the citation basis on the scorecard) was **not** implemented. The claim row records each citation's `reference` string, but a run-`citations`-dict resolution and an in-answer refdef both record identically as `{"reference": "[1]", "url": …}` — the row carries no separable basis for that half of E3, and the handoff requires the label be data-driven from the row, never inferred. Recording provenance would change the certified claim-row/chain schema, which is beyond a LOW normalization repair. The basis that *is* distinguishable (`claim_citations` rows carry the literal reference `"captured claim_citations"`; inline links carry their full markdown) is already printed verbatim in the scorecard's per-claim citations dump. Any rendering change would also alter CLI run output for every run, breaking the byte-identical demo outputs above.

## Out of scope, untouched

E2 (audit-helper re-runnability), the gold pack, all grader semantics beyond the E1 normalization. Nothing published, sent, or spent; no live capture was needed or made.

## Found but not fixed

Nothing beyond the disclosures above. The three verdict movements and the boundary-detection note are consequences of the single normalization repair, listed here so the independent auditor judges them with full information rather than finding them cold.
