# 03 — Concept card (v3)

> Deliverable: recommendation, principles, trade-offs, limits. Keep it to one screen when presented. Iterate as the build teaches us things — log changes in DECISIONS.md.

## Name: **Receipts, not reviews**
Every claim the human sees comes with a receipt: something that was *executed* (a test that fails on base and passes on the PR, a byte comparison, a git ancestry check). No receipt means hearsay. Our first real receipt: 6 of the agent's 10 tests on #2234 pass on the old code, so they are claims with no receipt (L-03).
Tagline for the pipeline: *Prove · Predict · Sign.*
One-page visual version: `src/earned_trust/ui/card.html` (published as `card.html` on the live site, linked from the scoreboard).

## Recommendation (one sentence)
**Stop asking humans to read AI-written diffs. Have the AI *prove* what behavior changed, have the named human *predict* what should happen before seeing it, and treat every mismatch as the review.**

## Why line-by-line review is the wrong unit
- Agent PRs are mostly reviewed by no one: 98.2% of Codex-authored PRs in the AIDev dataset had no recorded review comment.
- Humans approve AI output more easily (automation bias): reviewers were more likely to approve Copilot-assisted code in a GitHub trial.
- A fluent AI explanation makes this worse — and PR text is a proven prompt-injection surface.
- So the unit of review should be the **behavior change**, not the line.

## How it works (the review factory: Prove → Predict → Measure → Refuse → Sign)
1. **Scope** — read the requirement (issue ID) and derive what *should* change, blind to the agent's story. PR text is quarantined: quoted as data, never given to a model as instructions (hidden payloads flagged: HTML comments, Unicode tag characters, zero-width text).
2. **Prove** — run tests on base and PR. Pass on PR and fail on base = a proven behavior change (catching test); pass on both = a placebo. Tag each change `intended` / `collateral` / `unexplained` against the requirement. Machine-verifiable files (regenerated snapshots) are cleared by byte comparison, so human minutes go to behavior.
3. **Predict** — for each change the human hasn't seen, the named human predicts the correct behavior *before* the reveal. A match is accepted with evidence; a mismatch is the review.
4. **Measure** — every screener is calibrated on *this* PR: planted bugs (mutants) in the changed regions measure the tests and the AI reviewer; one disclosed drill among the questions measures the human. Before a reviewer may clear anything in a region, it is backtested on that repo's own past regressions (Time Machine), and a trust ledger keeps per-region trust from executed events, withdrawn after an escape.
5. **Refuse** — what the requirement doesn't cover, or what the evidence can't settle, becomes a refusal: "I won't decide this", handed to the human as a question.
6. **Sign** — the human signs a review record (proven changes, refusals, predictions, drill result, calibration, evidence hashes, name), wrapped as a signed in-toto attestation anyone can verify and replay.

## Risk router: depth follows risk (`et tier <pr>` → `out/<pr>/tier.json`)
No score. Each PR's tier is the **highest tier any named rule sets**, and every rule quotes an executed fact and where it came from (a git command or an `out/` file). Each file also gets a lane, so the signer sees *why* they were asked to read this much, and where. The tier is inside the signed record.

| Tier | What the human does | Rules that set it (each cites an executed fact) |
| --- | --- | --- |
| **T0** machine-cleared | nothing | `byte-identical-regen` (generated file = our own regeneration, byte for byte); `template-output-consistent` (T4 check) |
| **T1** light check | skim tests/docs for claims | `light-check` (non-behavior files: tests, docs) |
| **T2** predict-then-reveal | answer questions before the reveal | `proven-behavior-change`, `unrequested-change` (collateral/unexplained), `refusal`, `placebo-tests`, `screener-below-bar` (tests < 80% of planted bugs), `no-track-record` |
| **T3** full read, required | read the flagged files line by line | `new-public-api` (one-way door: new public type, diagnostic ID or PublicAPI entry), `circuit-breaker` (region trust withdrawn after an escape), `no-execution-receipts` (behavior code, no base/head run), `machine-clearing-low` (< 50% of files) |

Results on the four PRs (from `out/<pr>/tier.json`):

| PR | Tier | Why | Files per lane T0/T1/T2/T3 |
| --- | --- | --- | --- |
| #2234 | **T3** (T2 without the circuit breaker) | `circuit-breaker`: `TypeCollector.cs` trust withdrawn after upstream #2106 escaped (`1a74a620`, merged with 0 reviews, reported ~10 months later) | 0 / 3 / 0 / 1 (the full read is 22 changed lines) |
| #2283 | **T3** (T2 without the circuit breaker) | same region, same escape | 0 / 3 / 0 / 1 (29 lines) |
| #2297 | **T2** | 3 proven behavior changes, 1 unexplained (CS0579 build break), 2 refusals | 228 / 2 / 7 / 0 |
| #2129 | **T3** | `new-public-api`: adds `public class GeneratedMessagePackFormatterAttribute` (`src/MessagePack.Annotations/Attributes.cs`) and diagnostics MsgPack019–022 (`AnalyzerReleases.Unshipped.md`); also no base/head test run, and machine clearing 2/28 | 2 / 15 / 0 / 11 |

**Circuit breaker.** An escape in a region raises that region to T3 automatically and keeps it there until trust is earned back (the trust-ledger rule: 3 later calibrated reviews that catch every planted bug, tests ≥ 80%). It is driven by executed escape events, not by a person noticing. Anthropic's Oct 2026 write-up of their own AI-review process says “We don’t yet have circuit breakers that tighten approval when those numbers move” and calls it an open need ([claude.dev](https://claude.dev/blog/solving-code-review-at-anthropic/)).

## Principles (and how they balance the five forces)

| # | Principle | Balances |
| --- | --- | --- |
| P1 | **Evidence or it didn't happen.** Only executed checks count as proof; LLM opinions are labelled hearsay. | Hallucination, quality |
| P2 | **Confidence is measured, never self-reported.** Planted-bug catch rate per PR. | Confidence |
| P3 | **The AI may refuse.** Anything the requirement doesn't cover is a question for the human, not an approval. | Risk, accountability |
| P4 | **The story is untrusted input.** Intent is derived blind, then compared; text that instructs the reviewer is flagged. | Security, transparency |
| P5 | **Predict before you see.** The human commits to an expectation before the reveal, so the AI can't anchor them. | Automation bias, accountability |
| P6 | **Spend human minutes on risk.** Machine-verifiable change is cleared automatically. | Throughput vs risk |
| P7 | **Every signature is replayable.** The record shows what the signer knew when they signed. | Transparency, accountability |
| P8 | **Trust is earned on history.** A reviewer is replayed on the repo's own past regressions before it may clear anything there; trust is kept per region from executed events and withdrawn after an escape. | Confidence, risk |
| P9 | **Calibrate every screener, the human too.** Tests and the AI get planted bugs; the human gets a disclosed drill. The signature carries both results. | Automation bias, accountability |
| P10 | **The record is the product.** A signed, verifiable attestation (what changed, what was proven, what was refused, what the human predicted, who signed), not a PR comment. | Transparency, accountability |

## The judges' three questions
**What would make you not trust your own output?** Stop rules, each measured on the PR, not self-reported:
- The tests catch fewer than 80% of the bugs we plant in the changed code → they can't clear that region (#2234: tests 6/10; tests + Gemma 10/10).
- An agent test that passes on the old code is a placebo and doesn't count (#2234: 6 of 10).
- The requirement isn't supported by the history → refusal (#2234: the reported regression is not in this code's history, so "Is #2234 fixed?" is refused).
- An AI "clean" is not evidence: Gemma reported 0 findings on #2234 (2 runs) while the receipts prove 3 behavior changes.
- The human misses the disclosed drill → the signature carries a `MISSED DRILL` flag.
- A region had an escape → circuit breaker, T3 until trust is earned back (`TypeCollector.cs`).
- Our own failures are logged: `docs/FAILURE_MODES.md` (F-01…F-47).

**Who owns the decision?** The named human who signs the record. The AI proves, asks and refuses; it never approves, and a bot can't fill the human slot. The record says what the signer predicted before the reveal, what was refused to them, and their drill result, so the accountability is specific. In a team, the person who prompted the agent is accountable for the PR too.

**How would this scale?** Depth follows risk: most change should land in T0/T1 (#2297: 228 of 237 files machine-cleared, 9 for a human), and only named rules can send a PR to T3. Compute replaces human minutes: the base + head test runs took 27.8 s (#2234), 21.5 s (#2283) and 37.0 s (#2297) of test time (TRX timestamps; build time and the planted-bug runs not measured). The trust ledger means regions with a track record need less, and regions with an escape need more, automatically. Honest limit: it needs a sandbox that can build and test base and head for every PR.

## Trade-offs (be explicit — judges asked for these)
- **Cost:** generating and running tests on base and PR (plus mutants) costs compute and minutes per PR. We trade CI time for human time.
- **Coverage:** we only prove behaviors we managed to test. Unproven areas are shown as *unknown*, not *safe*.
- **Human effort moves, it doesn't vanish:** the human answers a few sharp questions instead of reading everything.
- **Friction on purpose:** predict-before-reveal slows approval down slightly; that friction is the safety feature.
- **False alarms:** catching tests can fail for flaky reasons; needs filtering (Meta uses rule-based + LLM assessors).
- **Drills cost attention:** a drill costs about a minute per review, and people dislike forcing functions (Buçinca et al.). We disclose that a drill exists and keep it to one per review.
- **Backtests need history:** the Time Machine only works where the repo has known, traceable regressions. A new repo starts with "no track record" = low trust, not high.
- **Machine clearing only helps mechanical change:** #2297 drops from 237 files to 9 for the human; the hand-written feature #2129 clears only 2 of 28. For real features, the human load stays real.

## The record as evidence (B6: `et attest` / `et verify`)
The review record is wrapped in an **in-toto Statement** (subject = the PR head commit, `predicateType: https://earned-trust.dev/review/v0.1`), with every executed evidence file listed as a hashed material, and signed with `ssh-keygen -Y sign`. `et verify` checks the signature, re-computes the record hash, re-hashes every evidence file and checks the subject commit. Changing one evidence byte, or flipping one verdict in the statement, makes it INVALID (tested).

What each field is evidence *for* (it supports these obligations; it doesn't make anyone compliant on its own):

| Record field | DORA Art. 9 ICT change management (EU finance, since Jan 2025) | SLSA Source L4 (two-party review) | EU Product Liability Directive (software, from 9 Dec 2026) |
| --- | --- | --- | --- |
| `requirement`, `blind_intent`, `requirement_link` per change | change is documented and its purpose assessed | review is tied to a specific change | what the product was meant to do |
| `ledger` / behavior changes with TRX hashes (base vs head) | change is **tested**, with recorded results | "successful test runs" in the attestation | state of the art at release: what was verified |
| `refusals`, `not_checked`, `hearsay` | risk assessed; open risks explicit | — | known limitations disclosed, not hidden |
| `calibration` (planted bugs: tests, AI) + `human_calibration` (drill) | controls are verified to work, per change | reviewer is not a rubber stamp | diligence of the review process |
| `signoff` (named human, predictions committed before reveal, residual risk) | **approved** by an accountable person; segregation of duties (author = agent, approver = human) | second party is a named human | who accepted which risk, and when |
| `quarantine` (author text quoted, never obeyed) | integrity of the review input | — | — |
| in-toto Statement + signature + `et verify` | change record is tamper-evident and replayable for audit | verifiable provenance of the review | evidence a defendant can produce |

Demo limitation: the signing key is a generated demo key (`out/attest/`), not a person's identity. In production the signer is the named reviewer's key (or Sigstore keyless with their OIDC identity).

## Receipts by layer (frontend, backend, security, performance)
The sample is a backend library, so only the backend row is built. The method is the same in every layer: an executed receipt replaces opinion; what no receipt can settle becomes a question, asked before the reveal.

| Layer | Executed receipt (base vs head) | Status here | What stays a human question |
| --- | --- | --- | --- |
| Backend | catching tests; regenerated-output byte compare; consumer compile check (found CS0579 on #2297); public API diff (`new-public-api` rule) | **built** | is this the intended contract? |
| Frontend | visual snapshot diff, accessibility-scan delta, recorded user-flow trace | not built | "is this the intended look/flow?", predicted before seeing the screenshot |
| Security | author text quarantined (**built**); site secret scan (**built**); SAST *delta* (only new findings); authz tests as catching tests; always-T3 paths (auth, CI workflows, crypto) | partly built | is this risk acceptable? |
| Performance | benchmark base vs head, run twice to get a noise band; a change outside the band is a behavior change | not built | is the trade worth it? |

A "generalist reviewer" is then one router over layer-specific receipt makers. The LLM scopes and asks; it never certifies.

## Outcome metrics (what the factory reports over time)
Outcomes, not activity. Measured now on 4 PRs, all from executed runs:
- **Escapes per region** (trust ledger: 1 escape, `TypeCollector.cs`; 28 events in Aiven Postgres).
- **Placebo rate per agent** (6 of the 15 tests the agents added).
- **Catch rate per screener on planted bugs** (#2234: tests 6/10, Gemma 9/10, together 10/10).
- **Drill result per signer** (1 disclosed drill on #2234; the result goes into the signature).
- **Human minutes per PR** (estimate: #2297 ~124.5 → ~10.5 min).
- **Guardrail: revert / incident rate** of merged PRs. Every escape becomes a Time Machine backtest (judged by execution, not by an LLM) and trips the circuit breaker. Not measured here: these PRs have no production history.

## Where this sits (prior art)
| What exists | What it does | Where it stops | What we add |
| --- | --- | --- | --- |
| Vendor AI reviewers (CodeRabbit, Copilot, Bugbot…; CodeRabbit field study, 56.3% of comments rejected: [arXiv 2607.03316](https://arxiv.org/abs/2607.03316)) | line comments, summaries | answers "what's wrong?", not "what can a human sign?"; no measured confidence | measured screeners, refusals, a signed record |
| Meta Diff Risk Score ([arXiv 2410.06351](https://arxiv.org/abs/2410.06351)) | an LLM risk score gates risky diffs | a score, explained after the fact | a tier made only of named rules over executed facts |
| Behavior-diff tools: Meta JiTTests, ADAPT ([arXiv 2611.16114](https://arxiv.org/abs/2611.16114)), DiffTestGen, BeTell | prove behavior changed between base and head | stop at "it changed": no requirement link, refusal, human prediction or signature | our *Prove* step builds on them, then Predict → Measure → Refuse → Sign |
| Anthropic's AI code-review process ([claude.dev, Oct 2026](https://claude.dev/blog/solving-code-review-at-anthropic/)) | risk tiers decide how many humans review | no circuit breakers yet (their words: “We don’t yet have circuit breakers that tighten approval when those numbers move”); verifier agents are LLMs checking LLMs | a circuit breaker driven by executed escapes; LLM output stays hearsay |
| Trust-Calibrated Code Review ([arXiv 2606.01969](https://arxiv.org/abs/2606.01969)) | practitioners: review is a trust-calibration problem | a design study | calibration built in: planted bugs for tests and AI, a drill for the human, per-region trust |

*Vendors make the AI find more. Behavior-diff research proves what changed. Anthropic routes by risk. Nobody closes the loop: measured screeners, a human who commits before seeing, refusals, a signed record, and trust that tightens itself after an escape.*

## Limits (what this does NOT solve)
- Doesn't judge architecture fit or long-term maintainability well.
- Requires a buildable, testable codebase (needs a sandbox that can run base and PR).
- Questions are only as good as the requirement; a vague issue yields vague scope.
- Planted bugs measure catch rate for bug *types we can plant*, not unknown unknowns.
- Not a substitute for security review of secrets/infra changes.

## The demo in one sentence
On `ju26-issue-2234`, an AI reviewer finds nothing (Gemma, 0 findings, 2 runs), but the receipts show that the reported regression isn't in this code's history, that 6 of the agent's 10 tests are placebos (they pass on the old code), and what the PR *really* changes (the analyzer no longer crashes on duplicate/mixed keys; the generator keeps the first duplicate-key member, silent only if MsgPack005 is downgraded); the human predicts before the reveal, one of the questions is a disclosed drill, the system refuses to call #2234 fixed, and the decision is signed as a verifiable attestation.

## Headline numbers (all executed; sources in `HANDOFF.md` §3)
- **6 of 10** of the agent's tests on #2234 are placebos (pass on base); **6 of 15** across all agent PRs.
- Planted bugs on #2234: tests catch **6/10**, Gemma **9/10**, together **10/10**.
- #2297: **237 → 9** files for the human (222 regenerated snapshots byte-identical), plus a CS0579 build break the agent's tests missed.
- Time Machine: the agent's tests, replayed on the 2024 commit that introduced the bug (`1a74a620`, merged with 0 reviews): **2 go red** (would-have-caught); the bug reached a user ~10 months later.
- Risk router: #2129 → **T3** (new public API: `GeneratedMessagePackFormatterAttribute` + MsgPack019–022); #2234 and #2283 → **T3** by the circuit breaker (T2 without it); #2297 → **T2**.
- Injection: a hidden instruction in a PR description made a naive reviewer drop a real finding in 2 of 3 runs (4/6 vs 6/6 planted bugs caught). Our pipeline never gives PR text to a model.
