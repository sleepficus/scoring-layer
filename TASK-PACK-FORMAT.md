# Task-pack data contract

The caller supplies JSON files. No core edit or provider-specific grader branch is needed. Every source in a synthetic fixture uses invented data; live capture preserves the real returned bytes separately.

## Task card

`task_card` contains `id`, positive `freshness_bound_hours`, `cost_bound` with nonnegative `max_credits` and `max_tokens`, and nonempty `questions`. Each question has a unique `id`, `question`, nonempty `required_elements` string list, and optionally its own positive `freshness_bound_hours`. Extra descriptive fields are sealed with the card. Criteria are never inferred from the answer after grading.

## Synthetic fixture

Start from `fixtures/session2_claim_support.json`. The root has `synthetic: true`, `task_card`, `runs`, and optional `human_decisions`. Each run has `run_id`, `agent_label`, `started_at`, `final_answer`, and `fetches`. Each fetch supplies `url`, `relied_on`, `question_ids`, `tokensUsed`, and `response` with `creditsUsed` and `data.markdown` plus `data.metadata` (`sourceURL`, `statusCode`, `cachedAt`, `cacheState`). Missing synthetic spend is rejected. The old Firecrawl-shaped fixture input remains supported.

`claims` is always re-extracted from the actual final answer; supplied pregraded claims cannot hide sentences or inject SUPPORTED results. Optional `citations` maps labels such as `1` to exact captured URLs. Inline Markdown links and reference definitions in the answer also work. `claim_citations` can map a stable `<run_id>:claim:<n>` ID to captured URL(s). No citation is inferred merely from question assignment. Cite the captured source URL (including any meaningful query string); when multiple captured documents share a URL, all are bound and conflicting support is sent to review; live plans reject duplicate requested URLs.

## Live plan and capture

Start from `fixtures/live_keyless_example_plan.json`. A plan contains one `task_card`, `run_id`, `agent_label`, `final_answer`, `fetches` with `url`, `question_ids`, `relied_on`, and optional `citations`, `judge_decisions`, `notes`. `capture-live` seals the card, records the request plan, makes fixed keyless markdown-only Firecrawl reads, then writes a complete/blocked/incomplete capture packet. It does not write the answer with a model. The final answer is caller-supplied and labeled accordingly.

Load the resulting packet through `run --pack`. Only COMPLETE captures with consistent request/response/normalized evidence can be scored. Raw bytes, SHA-256, request/response times and provider fields are preserved. A stored capture is not a substitute for independent provenance review; it is a reproducible evidence record. Missing live credits/tokens/cache metadata remain explicitly unknown. The account-free route prevents paid fallback independently of any scoring bound.

## Optional judge decisions

See `fixtures/session2_judge_demo.json`. Add `judge_decisions` to a run. A row requires `claim_id`, `verdict`, `reasoning`, and `judge` containing `seat`, `model`, `reviewed_at` (ISO timestamp). A SUPPORTED or CONTRADICTED verdict requires `passages`, each with integer `fetch_index`, `start`, `end` and exact `text` from a successful bound fetch. An UNSUPPORTED row requires nonempty `absence`. The grader adds document URL/hash and rejects invented passages, unknown/duplicate claims or judge decisions on already deterministically settled claims.

Only semantic residue with `needs_judge: true` accepts a judge decision. JUDGE rows live beside the original deterministic rows, retaining the original verdict. They never change the deterministic counts, denominator or review precision. This package provides import/validation; it makes no model API calls. Actual judge correctness is still an independent review question. The included judge example is explicitly synthetic, not a claim that a real seat reviewed it.

## Review decisions

Each `human_decisions` entry has an emitted `flag_id`, its matching `grader`, `decision` (`confirm` or `kill`), and optional `note`. Synthetic examples must say they are invented, as the included pack does. Duplicates, unknown flags and wrong graders are refused before chain writes. The CLI records decisions and prints their chain positions. The later queue UI can write the same record shape; no UI is built in this session.

## Gold pack boundary

The future Opus seat supplies gold tasks, reads and adversarial cases as data; none are present in this candidate. Synthetic demonstration decisions do not certify the grader. Data authors should keep source acquisition and gold interpretation separate, then use an independent seat to check both.
