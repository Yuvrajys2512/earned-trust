# 03 — Concept card (v2)

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
- Injection: a hidden instruction in a PR description made a naive reviewer drop a real finding in 2 of 3 runs (4/6 vs 6/6 planted bugs caught). Our pipeline never gives PR text to a model.
