# Claim lane builder self-review

Exact request and all enclosed hand-off/spec/build/progress context read before implementation. Parent owns backup/recovery and final candidate integration. This lane owns only scoring/claims.py, tests/test_claims.py and claims-* receipts.

Implemented rule-based factual prose candidates with exact final-answer character spans and stable IDs. Compound verbal clauses retain their raw text and label inherited subject context. Citations bind only to captured document URLs, including inline links, reference definitions, captured reference maps and captured per-claim attribution. No legacy citation is invented from question IDs or relied_on.

Deterministic evidence rows retain actual fetched passage text, character offsets, URL, fetch index and SHA-256. Exact complete statements and narrow subject/relation/scalar/unit assertions can support; a different scalar with identical subject, relation and unit is contradicted. No match is recorded as UNSUPPORTED by deterministic checks and semantic residue is explicitly needs_judge. Uncited or unfetched references declare the evidence absence and fail binding.

Judge decisions are imported data with seat/model/time and reasoning. Supported/contradicted judge rows require actual text at exact offsets in a bound successful fetch; unsupported rows require explicit absence. Unknown IDs, duplicate decisions, non-residue decisions and invented/uncited passages are rejected. JUDGE rows and counts never replace or join deterministic counts.

Self-review found and repaired two edge cases before handoff: independently cited compound clauses were borrowing sibling citations; bracketed source qualifications could disappear during reference cleanup. Targeted tests now pin both. Reviewed negative/qualified/other-subject source scenarios and actual passage offsets; all pass in claims-tests.log.

The recovered legacy fixture answers have no explicit citations. Their claims are extracted and emitted UNSUPPORTED with citation absence rather than silently assigned supporting URLs. See claims-legacy-fixture-replay.json.

Limits are present in every result: this rule-based extractor cannot guarantee complete atomic fact extraction for tables, pronouns, nested claims or multilingual prose; deterministic paraphrase entailment is unmeasured. A semantic false flag can be exposed naturally using monthly vs per month, without injecting an error in code. The code validates judge receipts, not the semantic correctness of the external judge.

Builder test result: 32 tests PASS, exit 0. Test output and code hashes are in claims-tests.log and claims-receipt.json. Independent review has not yet occurred; this is no certification. Questions for Stephen: none.
