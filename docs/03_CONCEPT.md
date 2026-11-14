# 03 — Concept card (DRAFT v0.1)

> Deliverable: recommendation, principles, trade-offs, limits. Keep it to one screen when presented. Iterate as the build teaches us things — log changes in DECISIONS.md.

## Name: **Receipts, not reviews**
Every claim the human sees comes with a receipt: something that was *executed* (a test that fails on base and passes on the PR, a byte comparison, a git ancestry check). No receipt means hearsay. Our first real receipt: 6 of the agent's 10 tests on #2234 pass on the old code, so they are claims with no receipt (L-03).
Tagline for the pipeline: *Prove · Predict · Sign.*

## Recommendation (one sentence)
**Stop asking humans to read AI-written diffs. Have the AI *prove* what behavior changed, have the named human *predict* what should happen before seeing it, and treat every mismatch as the review.**

## Why line-by-line review is the wrong unit
- Agent PRs are mostly reviewed by no one: 98.2% of Codex-authored PRs in the AIDev dataset had no recorded review comment.
- Humans approve AI output more easily (automation bias): reviewers were more likely to approve Copilot-assisted code in a GitHub trial.
- A fluent AI explanation makes this worse — and PR text is a proven prompt-injection surface.
- So the unit of review should be the **behavior change**, not the line.

## How it works (the review factory)
1. **Scope** — read the requirement (issue ID) and derive what *should* change, blind to the agent's story.
2. **Prove** — generate catching tests: pass on base, fail on PR. Each is a proven behavior change. Tag: `intended` / `collateral` / `unexplained` against the requirement.
3. **Clear** — machine-verifiable parts (regenerated files, formatting) are auto-cleared with evidence.
4. **Calibrate** — plant hidden known bugs in the changed regions; the AI reviewer's catch rate on *this* PR is its confidence for *this* PR.
5. **Ask** — for each `collateral`/`unexplained` change, ask the named human to predict the correct behavior *before* revealing the PR's behavior.
6. **Sign** — the human signs a review record: proven changes, refusals, predictions, answers, evidence hashes, name.

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

## Trade-offs (be explicit — judges asked for these)
- **Cost:** generating and running tests on base and PR (plus mutants) costs compute and minutes per PR. We trade CI time for human time.
- **Coverage:** we only prove behaviors we managed to test. Unproven areas are shown as *unknown*, not *safe*.
- **Human effort moves, it doesn't vanish:** the human answers a few sharp questions instead of reading everything.
- **Friction on purpose:** predict-before-reveal slows approval down slightly; that friction is the safety feature.
- **False alarms:** catching tests can fail for flaky reasons; needs filtering (Meta uses rule-based + LLM assessors).

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
On `ju26-issue-2234`, the system finds that the regression described in #2234 isn't in this code's history, shows that 6 of the agent's 10 tests are placebos (they pass before the change), proves what the PR *really* changes — the analyzer no longer crashes on duplicate/mixed keys, and the generator now keeps the first of two duplicate-key members — flags that as a real fix for an *unrequested* bug, asks the human what duplicate keys *should* do, and records the signed decision.
