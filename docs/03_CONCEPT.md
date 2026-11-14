# 03 — Concept card (DRAFT v0.1)

> Deliverable: recommendation, principles, trade-offs, limits. Keep it to one screen when presented. Iterate as the build teaches us things — log changes in DECISIONS.md.

## Working name (pick one in Round 0)
- **Prove · Predict · Sign**
- **Receipts, not reviews**
- **The human is the oracle**
- **Earned, not asserted**

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

## Limits (what this does NOT solve)
- Doesn't judge architecture fit or long-term maintainability well.
- Requires a buildable, testable codebase (needs a sandbox that can run base and PR).
- Questions are only as good as the requirement; a vague issue yields vague scope.
- Planted bugs measure catch rate for bug *types we can plant*, not unknown unknowns.
- Not a substitute for security review of secrets/infra changes.

## The demo in one sentence
On `ju26-issue-2234`, the system finds that the regression described in #2234 isn't in this code's history, shows that 6 of the agent's 10 tests are placebos (they pass before the change), proves what the PR *really* changes — the analyzer no longer crashes on duplicate/mixed keys, and the generator now keeps the first of two duplicate-key members — flags that as a real fix for an *unrequested* bug, asks the human what duplicate keys *should* do, and records the signed decision.
