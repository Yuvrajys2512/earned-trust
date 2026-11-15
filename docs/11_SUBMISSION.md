# 11 — Submission text (draft, Sat 14 Nov ~18:50 Helsinki; numbers refreshed Sun 15 Nov ~00:30)

Paste-ready. Every number is from `HANDOFF.md` §3 or `out/<pr>/tier.json` (executed sources). Fill the remaining `TODO` link (video) before submitting. Submit by **Sun 09:30 Helsinki**.

- Live demo: https://yuvrajys2512--earned-trust-receipts-site.us-east.modal.run
- Concept card: https://yuvrajys2512--earned-trust-receipts-site.us-east.modal.run/card.html
- Try to fool it (interactive): https://yuvrajys2512--earned-trust-receipts-site.us-east.modal.run/fool.html
- Repo: https://github.com/Yuvrajys2512/earned-trust
- Video (≤ 3 min): TODO
- Team: Yuvraj Srivastava (solo)

---

## Title
**Receipts, not reviews** — Prove · Predict · Sign

## One-liner (short description field)
The AI proves what behavior changed. The human predicts what should happen before seeing it. Every mismatch is the review, and the result is a signed record anyone can verify.

## Description

**Problem.** Agent-written PRs arrive faster than people can read them, and a fluent AI explanation makes approval easier, not safer. "Read every line" doesn't scale, and "trust the AI reviewer" isn't accountability. So we changed the unit of review from the *line* to the *behavior change*.

**How it works (the review factory: Prove → Predict → Measure → Refuse → Sign).**
1. **Prove.** Run tests on the base commit and on the PR. A test that fails on base and passes on the PR is a *proven* behavior change. A test that passes on both is a *placebo*: it proves nothing about this PR. Regenerated files are rebuilt and byte-compared, so a machine clears them. An LLM claim with nothing executed behind it is labelled *hearsay*.
2. **Predict.** For each proven change, the named human picks what *should* happen. The prediction is locked, and only then is the actual behavior revealed. A match is accepted with evidence. A mismatch is the review.
3. **Measure.** Confidence is measured, never self-reported: we plant known bugs in the changed code and score the tests and the AI reviewer on *this* PR. One question is a disclosed drill for the human, like test images shown to airport screeners. Trust is kept per file on history, and it's withdrawn after an escape.
4. **Refuse.** Anything the requirement doesn't cover, or that the evidence can't settle, becomes "I won't decide this": a question for the human, never an auto-approval. PR text is untrusted input. It's quoted as data and never given to a model.
**Route (depth follows risk).** An explainable risk router sets how much human review a PR gets: T0 machine-cleared · T1 light check · T2 predict-then-reveal · T3 full read. There is no score: a tier comes only from named rules, and each rule quotes an executed fact (a git diff, a test run, a byte compare, the trust ledger). A **circuit breaker** raises a region to T3 after an escape until trust is earned back. The tier and its reasons are inside the signed record.
5. **Sign.** The human signs a review record listing what was proven, refused and *not* checked, plus their predictions, the drill result and residual risk. It's wrapped as an in-toto Statement and signed with `ssh-keygen`, so anyone can verify it.

**What it found on the challenge's agent PRs (all executed).**
- **#2234 (main demo):** an AI reviewer (Gemma) reports **0 findings** in 2 runs. The receipts show that **6 of the agent's 10 tests are placebos**, and the reported regression is **not in this code's history**, so the system **refuses to call #2234 fixed**. Planted bugs: tests catch **6/10**, Gemma **9/10**, together **10/10**. **Time Machine:** the bug came from upstream PR #2106, which a maintainer merged without a review. Replayed on that commit, the agent's own tests go red (2 red): right tests, wrong commit, ~10 months late.
- **#2297:** **237 files → 9** for the human (228 machine-cleared, 222 byte-identical snapshots), ~124.5 → ~10.5 min (estimate). It also found a **CS0579 build break** for users who already excluded their resolver.
- **#2283:** the crash is fixed, but an **unrequested global filter** hides real MsgPack004 errors (shown by reverting only the filter).
- **#2129:** risk router **T3, full read**: it adds new public API (`public class GeneratedMessagePackFormatterAttribute`, diagnostics MsgPack019–022), a one-way door. Machine clearing clears only **2/28** files. That's the method's honest boundary on hand-written features.
- **Risk tiers:** #2234 and #2283 are **T3** by the circuit breaker (`TypeCollector.cs` lost trust after the 2024 escape; T2 without it, and the full read is 1 file, 22 changed lines on #2234). #2297 is **T2**.
- Across all PRs: **6 of the 15** tests the agents added are placebos.
- **Prompt injection:** with a description hiding instructions, a naive reviewer that read it caught **4/6** planted bugs vs **6/6** without it, and dropped a real finding in 2 of 3 runs. Our pipeline flags the payloads and never passes PR text to a model.

**The judges' three questions.** *What would make you not trust your own output?* Measured stop rules: tests under 80% of planted bugs can't clear a region; placebo tests don't count; a requirement the history can't support is refused; an AI "clean" isn't evidence; a missed drill flags the signature; an escape trips the circuit breaker (our own failures: F-01…F-47). *Who owns the decision?* The named human who signs; the AI proves, asks and refuses, never approves. *How would this scale?* Most change lands in T0/T1 (#2297: 228/237 files machine-cleared); base + head test runs took 21.5–37.0 s per PR (TRX timestamps; build time not measured); regions with a track record need less, regions with an escape need more.

**Why a judge should care.** The signed record is evidence toward DORA Art. 9 change management and SLSA two-party review. It supports those audits; it doesn't make anyone compliant. It records what the signer knew, what they predicted, and what was not checked.

**Honest limits.** It's weak on architecture fit and maintainability. It needs a buildable, testable repo. Planted bugs only measure known bug types. Predict-before-reveal adds friction on purpose. Unproven behavior is shown as *unknown*, never *safe*. The demo signing key is not a personal identity.

**Deliverables.** Concept card (`/card.html`, `docs/03_CONCEPT.md`), live walkthrough (`docs/10_WALKTHROUGH.md`), lessons log (`docs/LESSONS_LOG.md`, L-01…L-28), failure modes (`docs/FAILURE_MODES.md`, F-01…F-47), decision log (`docs/DECISIONS.md`), video.

**Verify it yourself.**
```bash
B=https://yuvrajys2512--earned-trust-receipts-site.us-east.modal.run
curl -sO $B/2234/attestation/statement.json -sO $B/2234/attestation/statement.json.sig -sO $B/attest/allowed_signers
ssh-keygen -Y verify -f allowed_signers -I reviewer@earned-trust.example -n earned-trust-review -s statement.json.sig < statement.json
```

**Built with.** A Python orchestrator (`uv`, CLI `et`) driving the .NET CLI and git, with static HTML pages. Built with Claude Code as the coding agent.

---

## Partner sections

### Gemma (Gemma 4 31B via Google API)
Gemma does three load-bearing jobs, and each is measured by execution rather than by its own say-so:
1. **AI reviewer under calibration.** On 10 bugs planted in #2234's changed code it caught **9/10**, against **6/10** for the tests. The two catch *different* bugs: in the fields region the tests caught 0/3 and Gemma 3/3. Its catch rate on the PR is the confidence we show, never a self-report. On the real PR it found nothing (0 findings, 2 runs), and the receipts show why that isn't the same as "clean".
2. **Spec writer** (derives the review questions from requirement + diff + ledger). Prompts went v1 → v3, scored over 18 runs (15 answered): **0 invented test names**, recovered **3/3** of the human-found behavior changes on both PRs, and given executed git facts, **6/6 runs refuse** to call #2234 fixed (v1 never did).
3. **Injection foil.** As a naive reviewer that reads PR text, it caught 4/6 planted bugs vs 6/6 without the text. This shows why our pipeline quarantines PR text.

### Aiven (PostgreSQL)
The **trust ledger**. Every executed screener event (28 so far: test runs, planted-bug results, escapes) goes into `et_events`, and attested record versions go into `et_records`. Trust is computed **per file region from history**, and it drives the risk router's circuit breaker. `TypeCollector.cs` has trust **withdrawn** because of the 2024 escape, and it's restored only after 3 calibrated reviews with every planted bug caught and tests ≥ 80%. #2234 (tests 6/10) doesn't earn it back, and #2283's page inherits the warning because it touches the same file. With no history, a region shows "no track record", which counts as low trust.

### Modal
The **live demo URL** (`deploy/modal_app.py`) serves the scoreboard, the review pages, the budgets, the concept card and the signed attestations. Pages go through an allowlist and a secret scan before deploy. An attestation downloaded from the live site verifies with stock `ssh-keygen`. (Modal sandboxes for the test matrix were planned but not used: the tests ran locally.)

<!-- Not claimed: NVIDIA Nemotron (wired in, never ran: no key). OpenAI Codex: claim only if it was actually used to build (README says Claude Code). -->
