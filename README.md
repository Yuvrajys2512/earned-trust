# Receipts, not reviews — Earned Trust in AI Code (Junction 2026)

**Live demo:** https://yuvrajys2512--earned-trust-receipts-site.us-east.modal.run
(scoreboard → review pages for #2234, #2297, #2283 · attention budget for #2129 · [concept card](https://yuvrajys2512--earned-trust-receipts-site.us-east.modal.run/card.html) · signed attestations)

**Challenge:** How does AI code review keep pace with AI-written code, while humans stay accountable for every change? (Tietoevry, Junction 2026)

**Our answer:** *The AI proves what changed. The human predicts what should happen. Every mismatch is the review.*
We don't ask anyone to trust the AI. We make it hand over receipts, and then we test the reviewer, and the human, on every PR.

## What it does
- **Prove.** Runs tests on the base commit and on the PR. Fails on base and passes on PR = a proven behavior change; passes on both = a placebo. Regenerated files are cleared by byte comparison. An LLM claim with no execution behind it is labelled hearsay.
- **Predict.** For each behavior change, the named human answers what *should* happen before the page reveals what the PR does. A mismatch is the review.
- **Measure.** Planted bugs in the changed code measure the tests and the AI reviewer on *this* PR; one disclosed drill measures the human; a Time Machine replays the checks on the repo's own past regressions; a trust ledger keeps per-region trust and withdraws it after an escape.
- **Refuse.** What the requirement doesn't cover becomes "I won't decide this", a question for the human. PR descriptions are untrusted data: quoted, scanned for hidden instructions, never given to a model.
- **Sign.** The review record (changes, evidence hashes, refusals, predictions, drill result, signer) is a signed in-toto attestation anyone can verify.

## Results on the 4 agent-written PRs (all executed)
| PR | What the receipts showed |
| --- | --- |
| **#2234** analyzer silent with `SuppressSourceGeneration` | AI reviewer (Gemma 4 31B): **0 findings** on the real PR (2 runs). Receipts: **6 of the agent's 10 tests are placebos**; the reported regression is **not in this code's history**, so the system refuses to call #2234 fixed. What the PR really changes: the analyzer no longer crashes on duplicate/mixed keys and the generator keeps the first duplicate-key member (silent only if MsgPack005 is downgraded). Planted bugs: tests **6/10**, Gemma **9/10**, together **10/10**. Time Machine: the bug came from `1a74a620` (upstream PR #2106, merged by its author with 0 reviews, 2024-12-26; reported ~10 months later); the agent's tests replayed there go red (would have caught it). |
| **#2297** `[ExcludeFromCodeCoverage]` on generated code | **237 files → 9** for the human (222 regenerated snapshots byte-identical), ~124.5 → ~10.5 minutes (estimate). Found a **CS0579 build break** for users who already mark their resolver; refuted the agent's "not available on netstandard2.0" claim. |
| **#2283** crash on closed generic value type | Crash fixed (2 catching tests), plus an **unrequested global diagnostic filter**: with only the filter reverted, real **MsgPack004 errors** come back; the agent's own test only passes because of the filter. |
| **#2129** formatter for a type in a referenced assembly | Machine clearing clears only **2 of 28** files: for hand-written features the human load stays real. The method's honest boundary. |

Across all four: **6 of the 15** tests the agents added are placebos. Injection: a hidden instruction in a PR description made a naive reviewer drop a real finding in 2 of 3 runs (4/6 vs 6/6 planted bugs caught); our pipeline never hands PR text to a model.

## Verify it yourself
Each review page links its `attestation/statement.json` and `.sig`; the demo public key is at `/attest/allowed_signers`. With stock OpenSSH:
```bash
B=https://yuvrajys2512--earned-trust-receipts-site.us-east.modal.run
curl -sO $B/2234/attestation/statement.json -sO $B/2234/attestation/statement.json.sig -sO $B/attest/allowed_signers
ssh-keygen -Y verify -f allowed_signers -I reviewer@earned-trust.example -n earned-trust-review \
  -s statement.json.sig < statement.json
```
Locally, `uv run et verify 2234` also re-hashes the record and every evidence file and checks the subject commit; changing one evidence byte or flipping one verdict makes it INVALID.

## How to run
Needs Python ≥ 3.11 with `uv`, .NET SDK 8 + 9, git, and a clone of the challenge repo (read-only).
```bash
source scripts/env.sh && export MSGPACK_REPO=/path/to/junction26-messagepack-csharp
uv run et --help
# rebuild pages from existing evidence in out/
uv run et trust && for p in 2234 2297 2283; do uv run et record $p; uv run et attest $p; done && uv run et index
# full pipeline for one PR (dotnet; slow): facts, base-vs-head tests, planted bugs, drill
uv run et facts all && bash scripts/verify_2234_base.sh && uv run et prove 2234
uv run et calibrate 2234 --tests --reviewer gemma && uv run et drill 2234
# publish (file allowlist + secret scan, then Modal)
uv run et site && uv run modal deploy deploy/modal_app.py
```
The full regeneration sequence is in [HANDOFF.md](HANDOFF.md) §6.

## Partner tech actually used
- **Google Gemma 4 31B** (via Google API): the AI reviewer that gets calibrated with planted bugs (9/10), the AI spec writer (B2: 0 invented test names in 15 answered runs), and the naive reviewer in the injection experiment.
- **Aiven for PostgreSQL**: the trust ledger (per-region trust from executed events, withdrawn after the `1a74a620` escape).
- **Modal**: hosts the live site.
- NVIDIA Nemotron is wired as a reviewer option but **never ran** (no API key); no results are claimed.
- Built with **Claude Code** as the coding agent.

## Honest limits
- Unproven is shown as *unknown*, never *safe*. We only prove behaviors we managed to test.
- Planted bugs measure catch rate for bug types we can plant, not unknown unknowns.
- Machine clearing only helps mechanical change (#2129: 2 of 28).
- Needs a buildable, testable repo; weak on architecture fit and maintainability.
- The signing key is a generated demo key, not a person's identity. The record supports DORA Art. 9 / SLSA two-party-review evidence; it doesn't make anyone compliant.
- Minutes are estimates (changed lines ÷ 20/min) and are labelled so.

## Docs
- Concept card: [docs/03_CONCEPT.md](docs/03_CONCEPT.md) · Architecture: [docs/04_ARCHITECTURE.md](docs/04_ARCHITECTURE.md)
- Decision log: [docs/DECISIONS.md](docs/DECISIONS.md) · Lessons: [docs/LESSONS_LOG.md](docs/LESSONS_LOG.md) · Failure modes: [docs/FAILURE_MODES.md](docs/FAILURE_MODES.md)

Team: Yuvraj Srivastava (solo).
