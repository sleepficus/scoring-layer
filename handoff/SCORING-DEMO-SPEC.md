# Spec — The House Artifact: A Live Scoring Layer for Agent Work (Firecrawl Edition)

_Spec only, drafted 2026-10-27. No code, no outreach, nothing sent. Companion dossier: `hidden_files/factory-firecrawl-dossier-2026-10-27.md` — every pain claim below traces to a receipt there._
_The factory's house artifact: one build, re-skinned per company. Firecrawl is the first skin because their pain is confessed in writing._

---

## 1. Purpose — in Stephen's framing

Most companies putting agents to work have **no scoring metric that tells them whether the agents are actually succeeding with their product**. Firecrawl says it out loud, in a live job posting: the evaluation system doesn't exist, the metric "has to be invented," and "did that work?" gets harder every quarter. Latent proved the market wants this layer for model answers; the same layer for *agent work* — graded against the real sources the agent touched — is the foot in the door.

So the artifact is not a résumé claim ("I build evals"). It is a working scoring system, pointed at Firecrawl itself, that a hiring manager can watch grade a real agent's real web work — live, claim by claim, with every score opening to its receipts, and the grader's own accuracy printed on the same screen. **Show the system their posting describes, already running.** That is the delivery; everything else is packaging.

## 2. What it scores when pointed at Firecrawl

**The scenario.** A research agent is given ordinary, useful work of the kind Firecrawl customers hand agents daily: a sealed task card of factual questions whose answers live on live websites (product pricing, plan limits, docs facts, changelog dates). The agent works the way customers' agents work — Firecrawl `/search` to find pages, `/scrape` to fetch them, then it writes its answers with citations.

**The grading, per run:**

| Layer | Check | How |
|---|---|---|
| Fetch truth | Did each relied-on page come back as a real 200 document — or an error page, block page, or challenge wall returned *as* a document? | Deterministic: response `metadata.statusCode`, content-shape heuristics. No judge. |
| Freshness | Was the page's `cachedAt` inside the freshness bound the task card sealed before the run? | Deterministic: metadata vs. sealed bound. |
| Claim support | Is every factual claim in the agent's answer supported by a passage in the pages it *actually fetched*? Verdict per claim: SUPPORTED / UNSUPPORTED / CONTRADICTED — with the passage shown. | Judge seat reads claim + fetched markdown; verdict must cite the passage or declare its absence. |
| Completeness | Of the facts the task required, how many are missing from what the agent consumed (the `missing_markdown` failure, scored explicitly)? | Deterministic diff against the sealed task card's required elements. |
| Extraction fidelity | For any schema-shaped pulls: field present? value correct against a gold read? boilerplate contamination? | Gold comparison on the task pack's gold pages. |
| Cost truth | Credits + tokens spent ÷ claims that survived grading = **cost per verified fact**. | Arithmetic on receipts. |

**The outputs, live:** (a) a **review queue** — every flag lands the moment it fires, carrying the exact agent output, the criterion it broke, and the fetched source it should have matched; a human confirms or kills each flag in one click; (b) a **run scorecard** — per-dimension scores, never a naked composite: every number drills down to the claims, passages, and receipts under it (the Scorer doctrine); (c) a **grader scorecard** — the grading system's own precision, updated from the human confirmations, standing and visible (see §4).

## 3. Architecture — what already exists vs. what is genuinely new

**Already in the yard (verified on disk, 2026-10-27):**

- **The Excavator evidence chain** (`~/workspace/ultimate-eval-map/excavator/`) — an append-only, hash-chained store (9,972 records) with a 17-check checklist grader emitting PASS / FAIL / UNVERIFIABLE verdicts *with evidence attached*, and sealed, facts-only bundles. This is the artifact's spine: runs, grades, and queue decisions append to a chain nobody can quietly rewrite.
- **The Scorer doctrine** — no naked composite; every score opens to its receipts. The scorecard UI pattern already exists in the Excavator's Scorer surface.
- **Pre-sealing** — the Hub build's working pattern: criteria and task definitions sealed (hashed) before the run, so nobody — including the builder — can move the goalposts after seeing results.
- **The claim-ledger method** — Crucible Part One's discipline: every claim a system makes gets a ledger entry and a verdict; Part Two added live probing of the claims that matter.
- **The Tracker recorder** (`~/workspace/ops-board/record/`) — an events log + snapshot/refresh machinery recording agent work as it happens (commissioned by Stephen this morning as the tracker's extension; machinery on disk and recording). It supplies the *live* event stream the queue renders from.
- **Auditor seats** — the workbench's Opus / Fable / Spark seats, proven on Jobs 001–005 with per-run cost receipts, available for the claim-support judge passes.

**Genuinely new (the build):**

1. **A live run harness** — an instrumented agent+Firecrawl loop that captures at call time (prompts, Firecrawl requests/responses incl. `statusCode` / `cacheState` / `cachedAt` / `creditsUsed`, the agent's final claims), instead of grading fossils after the fact. The yard grades the past; this grades the present.
2. **A claim-support grader for research output** — claim extraction from the agent's answer, citation binding, passage-level support verdicts. The yard has checklist graders and claim ledgers, but nothing that binds a sentence to the fetched passage that must carry it.
3. **The live review queue UI** — flags appearing during the run, one-click confirm/kill, decisions written back to the chain. New surface, built on the recorder's event stream.
4. **The standing grader-precision scorecard** — the curriculum's Lesson-4 gap, named in the Excavator spec as missing from the whole yard: no standing FP/FN scorecard exists anywhere yet. This build closes it — for its own grader first.
5. **The Firecrawl task pack** — gold tasks with gold reads: questions, required elements, freshness bounds, gold passages, sealed before any run. Content work, not code — and the part that decides whether the grades mean anything.

## 4. The proof-of-honesty beat — why the grader is itself graded

This is the design's signature, and it comes from Stephen's own record, not from marketing.

In **Crucible Part Two (2026-10-27)**, live probing **REFUTED** Stephen's own Independence Audit tool: an approval from a checker the tool itself classified UNVERIFIED sailed through its gate as CLEAN — and the tool's own test suite *codified* the hole. The yard's one outright lying instrument was the one whose job was certifying honesty. The companion lesson, from the Evidence Binder probe the same day: its VERIFIED stamp meant "a hash matched an attestation" — never "the source supports the sentence."

Design consequences, non-negotiable in this build:

- The grader's precision is a **published, standing number on the demo's own scorecard**, fed by every human confirm/kill in the queue. If the grader cries wolf, the screen says so.
- Claim-support verdicts check **content against the fetched source**, never hashes, never attestations.
- The demo **includes one planted case where the grader is wrong** (see §5): the queue catches it, a human kills the flag, and the grader's precision ticks down on screen, honestly. A scoring system that has visibly survived being caught is worth more than one that merely claims accuracy. (Open Decision 4.)

## 5. The 3-minute demo shape

What a Firecrawl hiring manager watches. Pre-sealed, workshop-scale, rehearsed — the Hub demo discipline.

- **0:00–0:30 — Their words, then the sealed card.** The screen opens on their posting's own sentence — "the evaluation systems that tell us whether Firecrawl actually works" — then the task card: five factual questions, required elements, freshness bound, cost bound, *sealed with its hash before the run*. "The criteria were fixed before the agent started. Watch."
- **0:30–1:30 — A live run, graded as it happens.** The agent searches and scrapes via Firecrawl on camera. Claims stream into the scorecard as the agent writes them. Two deterministic flags fire in real time: the agent cites a page that came back as a 403 document (fetch-truth flag, the receipt from their own billing docs made visible), and a "current" price that came from a seven-hour-old cache (freshness flag).
- **1:30–2:15 — The queue.** A claim is flagged UNSUPPORTED: left side, the agent's confident sentence; right side, the fetched markdown it supposedly rests on — the passage isn't there. Then the planted beat: one flag is *wrong* — the grader misread a legitimately supported claim. The reviewer kills it, and the grader scorecard's precision ticks down a point, live. Nobody hides it. That's the product.
- **2:15–3:00 — The scorecard and the close.** Run totals, each opening to receipts: claim-support rate, silent-failure catches, cost per verified fact. The grader's standing precision beside them. Close on their sentence, answered: "You asked who can invent the metric. This is the metric — running, on your product, with its own honesty on the board."

## 6. v1 is / is NOT

**v1 IS:** one task family (web research/extraction via Firecrawl) · one agent seat doing real work · deterministic fetch/freshness/completeness grading + judge-seat claim support · live queue with human confirm/kill · chained receipts for every verdict · grader precision tracked standing · a rehearsed 3-minute film + a live-runnable scorecard page.

**v1 is NOT:** not activation-reading or anything inside a model (Latent's moat; API seats can't, and the demo never implies otherwise) · not a general eval platform · not a Firecrawl integration or partnership pitch · not an application to the posting · not multi-agent (the crew enters in v2 skins) · not sent anywhere without Stephen's exact-text approval of the final package.

## 7. Build estimate & staffing

Roughly **6–8 working sessions**, mirroring the Excavator's sizing honesty (its pilot was estimated 7–8 and landed in that shape): task pack + sealing (1) · live harness (1–2) · deterministic graders (1) · claim-support grader (2) · queue UI + scorecards (1–2) · rehearsal + film (1).

Staffing rides the **Nov 1 API reset** (00:00 UTC), per the recorded factory doctrine: **Fable = the research brain** (task-pack design, gold reads, adversarial cases — she authors the questions the system must survive), **Opus = production** (harness, graders, UI). Sequenced inside the Nov 1 program alongside the Hub rehearsal re-run and the Excavator's independent audit — it does not jump that queue without Stephen's word. Independent audit before anything ships: an auditor seat that did not build it re-runs the gold tasks and attacks the grader (Stephen's Law 2 — builder never certifies).

## 8. Risks

- **Garbage gold, garbage grades.** The task pack is the foundation; mitigated by Fable-authored gold reads + independent re-verification of every gold fact before sealing.
- **Judge-seat variance.** Claim-support verdicts from a model seat will wobble; mitigated by deterministic-first grading, passage-citation required for every verdict, and the standing precision scorecard making wobble visible instead of hiding it.
- **Demo-agent strawman.** If the demo agent is too weak, the demo grades a puppet. Mitigated by using a real, current seat doing unscripted work inside the sealed tasks — failures must be *found*, not staged (the two deterministic flags in §5 are expected failure *classes*, rehearsed against real runs, not scripted lines).
- **Firecrawl-side costs and rate limits.** Real API use across build + rehearsals burns real credits; bounded by the cost-truth layer itself (every run receipted) and Open Decision 5.
- **Scope creep into a platform.** The house-artifact idea invites "make it general." v1 stays one task family, one skin; generality is earned by the second company, not assumed by the first.
- **The seat fills.** The posting has been open since July; if Firecrawl hires their evals lead before the demo lands, the artifact's target shifts from "the vacant seat's manager" to "the new lead's first external collaborator" — the pain statement survives the hire; the packaging changes. Named here so nobody is surprised.

## 9. Open decisions for Stephen

Each with Muse's recommendation labeled. None of these block the Nov 1 program's other workstreams; all of them are his to veto in one word.

1. **Which seat plays the demo agent?** — *Recommendation: a real mid-tier seat, not the strongest available.* The demo's credibility is catching ordinary, everyday failure; grading a flagship seat invites "rigged either way" readings.
2. **Task-pack turf: Firecrawl's own docs/pricing as the research target, or neutral third-party sites?** — *Recommendation: mostly neutral live sites, plus two Firecrawl-docs questions.* Pure own-turf reads as staged; pure neutral wastes the "pointed at YOUR product" beat.
3. **Film a live run, or run it live at delivery time?** — *Recommendation: film the rehearsed live run (Hub demo discipline), keep the scorecard page genuinely runnable so a manager can re-run it themselves.* Live-only risks a bad five minutes; film-only invites "was it real."
4. **Include the planted grader-error beat?** — *Recommendation: yes.* It is the Crucible story made visible, and it converts the demo's honesty from a claim into a demonstration. (If it reads as gimmick to you, it cuts cleanly.)
5. **Firecrawl spend: free tier only, or a small capped credit purchase for build + rehearsals?** — *Recommendation: start on the free tier; if rehearsals starve, a small capped purchase — flagged plainly because it rubs against your subscriptions-only rule, so it needs your explicit word, not my assumption.*
6. **House-neutral core, Firecrawl first skin — or Firecrawl-only build?** — *Recommendation: neutral core, Firecrawl task pack as the first skin.* The factory's whole economics is re-skinning; the second company should cost a task pack, not a rebuild.
7. **Where the package lives when it's ready: public repo + hosted scorecard (the Hub pattern), or private link sent to one named person?** — *Recommendation: the Hub pattern — public at package time, after claims re-verify and your exact-text approval — but the first send goes to one named human with the link, not a broadcast.*
8. **Who receives it first: the evals seat's hiring manager (name currently UNKNOWN), Peffer, or the partnerships/agent-experience surface?** — *Recommendation: decide after Fable's Nov 1 research pass names the actual humans; do not address a demo to a job title.* Held open deliberately — the dossier's one honest unknown.

---

_Spec ends. Build starts only on Stephen's word, inside the Nov 1 program's queue._

---

## Commission record — 2026-10-27 ~16:32 EDT (Stephen's word)

Stephen commissioned the build: "I think this in itself can be a deliverable for just about any company that is using AI because we can be like, hey, you can use this too and if you want, like a demo or more information, we actually produce the application. So I think the next thing for this would be to develop the application. And you can use Fable or whatever you want."

Decisions resolved:
- **#6 House-neutral core: DECIDED BY STEPHEN** — the artifact is a deliverable for any company using AI; Firecrawl is the first skin, not the product. Pitch shape in his words: "you can use this too — and if you want a demo or more information, we actually produce the application."
- **Staffing: delegated by Stephen** ("Fable or whatever you want"). Practical sequencing: deterministic core builds now on available seats; Fable joins at the Nov 1 reset for the task pack / gold reads / adversarial cases (her authored part per §7); Opus available for production passes in the same window.
- **#1 demo seat, #2 task turf, #3 film + runnable page, #4 planted grader-error beat (yes), #7 Hub pattern (public at package time, exact-text approval, first send to one named human): DECIDED BY CLAUDE under Stephen's standing delegation**, per the recommendations in §9, logged here as vetoable in one word each.
- **#5 Firecrawl spend: NOT decided by Stephen — default is free tier only.** Build and tests proceed on labeled fixtures + free tier; any capped credit purchase still needs his explicit word (subscriptions-only rule).
- **#8 first recipient: still held open** for the Nov 1 research pass to name the actual humans.

Build workspace: `~/workspace/scoring-layer/` (BUILD-SHEET.md + PROGRESS.md live there). Scope discipline unchanged: v1 = one task family, one skin; generality is earned by re-skinning, not assumed.

---

## Strategy note — 2026-10-27 ~16:35 EDT (Stephen's pivot, supersedes the per-company factory shape)

Stephen: "instead of trying to create custom things for every single company, this is an area of specialty where you specialize in… my brain fits pretty well and I'm actually very interested in this area so I want to increase my knowledge and everything on it."

What changes:
- **Specialty-first, not bespoke-per-company.** The specialty is agent auditing / scoring systems — the "did that work?" layer for companies whose agents run on trust because they have no instrument. One core artifact (this build), re-skinned per company with a task pack; dossiers become *pain research* (does this company feel the audit pain, in writing?) rather than commissions for custom builds.
- **The pain framing (Stephen's words):** early adoption ran on blind trust; now big companies are banning or restricting AI after losses and incidents. A company that has felt the money pain *knows* it needs the system — that felt pain is the focus, not companies that still think they're fine.
- **Knowledge goal is now explicit:** Stephen wants to deepen his own expertise in this area (evals/auditing), not just ship artifacts. The yard's 7-lesson evals curriculum (~/workspace/evals-curriculum/CURRICULUM.md, built earlier, never started) is the standing asset for this.
- What does NOT change: the build (Session 1 running), the Nov 1 program, the exact-text rule on anything sent, and Avalara/Cresta materials already made (they become specialty proof pieces rather than templates for per-company custom work).
