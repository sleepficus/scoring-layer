# Claim lane repair — builder self-review for A1–A4

Builder: `/root/claims`, requested GPT-6.1 Sol Ultra. This is the builder's lap; independent closure remains required.

Read the independent consolidated FINDINGS.md, unchanged claim_adversarial_probes.py and failing-before log in full. Parent preserved the pre-repair candidate checkpoint. Restoring Session 1 cannot repair new Session 2 claim behavior because Session 1 has no claim module; the initial Session 2 candidate contains these defects. Repairs therefore address the four demonstrated behaviors directly.

- A1: A reference attached after sentence punctuation is consumed from subsequent sentence spans. Same-line trailing citations bind only to the preceding statement; a following sentence retains only its own references. The raw reported claim text still equals its exact final-answer span. Cross-line attribution is conservative and is not inferred.
- A2: Narrow scalar matching uses standard-library Decimal equality with comma/currency parsing. Source and claim spellings remain in raw claim/passage receipts. Equal decimal spellings support; truly unequal values still contradict, including decimal differences too small for binary float equality.
- A3: Markdown headings containing an explicit factual verb are extracted; the Markdown prefix is skipped as formatting and the retained text has exact character offsets into the answer. Ordinary headings such as Overview remain labels.
- A4: Source normalization no longer erases numeric square brackets, asterisks or other formatting markers. Answer citation cleanup is separate. A source note marker immediately following sentence punctuation stays attached to its passage, including whitespace-separated markers. Unresolved source qualification/reference markers become semantic residue with exact qualification passage receipts; nothing is marked supported by deleting those markers.

Self-review checked the repaired extraction control flow, complete source normalization, Decimal comparison and passage offsets. Added six builder regression methods covering the four findings plus separate follow-on citations, exact decimals, request counts, factual/nonfactual headings and five bracket/footnote combinations. No auditor file, external source, other module or prior evidence was changed. No network request or paid route was used.

Measured on Python 3.12.7: claim suite 38/38 PASS; unchanged auditor probes 9/9 PASS; full current candidate suite 135/135 PASS, all exit 0. Three actual CLI actions also exit 0: demo run, demo chain verification, and the former A1 citation-leak reproduction through CLI. Demo remains 2 SUPPORTED / 2 UNSUPPORTED / 1 CONTRADICTED, synthetic precision 66.7%; its chain verifies with 6 records. A1 CLI now has one supported first claim and an uncited unsupported second claim, with a 3-record verified chain.

Exact commands, outputs, source SHA-256 and machine-readable A1 rows are saved in claims-repair-receipt.json and claims-repair-*.log/json. The independent closure seat must evaluate this candidate; the builder does not certify it. Existing v1 extraction and semantic-entailment limits remain explicit. Questions for Stephen: none.
