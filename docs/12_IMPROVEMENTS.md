# 12 — Final-round improvements (research Sun 15 Nov ~00:10 Helsinki)

Goal: close the remaining brief gaps and set us apart, within the Sunday 05:00–09:30 window (video + submission take ~2 h of it).
Rule: every new number needs a command or an `out/` file behind it (AGENTS.md). Nothing here needs Gemma or a rerun of the pipeline.

## 1. What's new in the landscape (and where each falls short)

| Who / what | What it does | Where it falls short (our angle) |
| --- | --- | --- |
| **Anthropic, Claude Code team process** (Oct 2026, [claude.dev](https://claude.dev/blog/solving-code-review-at-anthropic/)) | A classifier sets a **risk tier** (low: 0 humans, medium: 1, high: 2); always-human paths; bots can't fill a human slot; the prompter is accountable; verifier agents vote on findings; **past incidents/reverts become a daily eval set**; reverts down >40% relative while merged PRs doubled | Their own admitted limits: **"no circuit breakers yet"** (nothing tightens approval automatically when reverts rise); detecting bad merges relies on people; reviews may not converge (50+ rounds). Voting verifiers are LLMs checking LLMs: by our definition still hearsay. No refusals, no human calibration, no signed record. |
| **Vendor AI reviewers** (CodeRabbit, Copilot, Bugbot, Greptile, Qodo) | Line comments, summaries | 56.3% of agentic review comments rejected, mostly false positives (arXiv 2607.03316, ~31k comments); precision 23–36% in vendor-run benchmarks; F1 drops from 0.80 to 0.04 on 150–600-line diffs (one Apr 2026 study). Answer "what's wrong?", never "what can a human sign?" |
| **Meta Diff Risk Score** ([2410.06351](https://arxiv.org/abs/2410.06351), explainability [2607.02782](https://arxiv.org/pdf/2607.02782)) | LLM risk score gates code freezes | Score explained only via attention highlights; hit the incident lines in ~54% of cases (top-2 hunks). This is the brief's "risk score nobody can explain". |
| **Behavior-diff tools**: Meta JiTTests, **ADAPT** ([2611.16114](https://arxiv.org/abs/2611.16114)), **DiffTestGen** ([2607.16024](https://arxiv.org/html/2607.16024)), **BeTell** ([GitHub](https://github.com/smythi93/BeTell)) | Run base vs head; tests that fail-to-pass, or traced runtime differences | Closest prior art to our *Prove* step (cite them). They stop at "behavior changed": no link to the requirement, no refusal, no human prediction, no signature, no calibration. Python-only (BeTell, DiffTestGen). |
| **Intent verification** (Tessl, Oct 2026, [blog](https://tessl.io/blog/we-stopped-reviewing-code-and-started-verifying-intent)) | Per-acceptance-criterion verdicts + screenshots/traces | Doesn't say how verdicts are produced; no measurements; self-reported. |
| **Blast-radius tools** (Qodo labels, code-review-graph, GitLab agent) | Static call-graph impact → review order | Static estimate, never measured; no data on whether it reduces misses. |
| **Frontend evidence** (Argos, Playwright MCP, ProofShot, Ito) | Screenshots/visual diff base vs baseline, runtime videos | Evidence without calibration, requirement link or sign-off. Useful as a *receipt type* for our frontend layer. |
| **Trust-Calibrated Code Review** (participatory study, [2606.01969](https://arxiv.org/abs/2606.01969)) | Practitioners want overview → file → snippet zoom, risk per line/file/chunk | Main conclusion: review is a **trust-calibration problem, not a diffing problem**, which is our thesis. Quote it. |
| **Accountability** ([2608.15678](https://arxiv.org/pdf/2608.15678)) | GitHub's Copilot agent can't approve/merge its own PR | Platform rule, not evidence of review. |
| Automation bias | Approval rate of reviewers rose 30.1% → 36.8% as they saw more AI PRs, inline comments −22% (2026 study, via secondary source) | Supports predict-before-reveal + drills. Mark as secondary if used. |

**Positioning line:** *Vendors make the AI find more. Behavior-diff research proves what changed. Anthropic routes by risk. Nobody closes the loop: measured reviewers, a human who commits before seeing, refusals, a signed record, and trust that tightens itself after an escape.*

## 2. Improvements, ranked (impact on judging × time)

### P0 — must do (≈2 h total)
1. **Push the repo** to a public GitHub repo (no secrets: `.env` is gitignored; check `git ls-files | grep -i env`), fill the TODO in `docs/11_SUBMISSION.md`. (10 min)
2. **Explainable risk router (the "Classifier" direction + "depth follows risk")** — `et tier <pr>` → `out/<pr>/tier.json`, a tier per PR made only of **named rules, each pointing to an executed fact**. No score. Suggested rules (verify each fact before using it):
   - **T0 machine-cleared:** file proven by byte comparison (222 snapshots in #2297).
   - **T1 light check:** human-written but mechanical, all behavior proven (rest of #2297 → 9 files).
   - **T2 predict-then-reveal:** proven behavior changes exist, or an unexplained/collateral change (#2234; #2283's global filter).
   - **T3 full read, required:** (a) **new public API surface** = one-way door: #2129 adds `public class GeneratedMessagePackFormatterAttribute` in `src/MessagePack.Annotations/Attributes.cs` and diagnostics MsgPack019–022 in `AnalyzerReleases.Unshipped.md` (verify: `git -C D:/msgpack show origin/ju26-issue-2129 -- src/MessagePack.Annotations/Attributes.cs`); (b) region trust withdrawn in the trust ledger (`TypeCollector.cs`); (c) machine clearing covers < X% of files (#2129: 2/28).
   - **Circuit breaker:** an escape in a region raises that region's tier automatically until trust is earned back (already the trust-ledger rule; make it visible as the tier rule). Say plainly: Anthropic's Oct 2026 post lists "no circuit breakers yet" as an open problem; ours is driven by executed escape events.
   - Show the tier + the rules that fired on the scoreboard (one column) and at the top of each review page. Record it in `record.json` (the signer sees *why* they were asked to read this much).
3. **Judges' three questions** as a block on the concept card (`docs/03_CONCEPT.md` + `card.html`) and in README:
   - *What would make you not trust your own output?* Stop rules, each measured: planted-bug catch on the PR below threshold (union < 10/10 → region goes T3); a missed drill flags the signature; a placebo-heavy test set (6/10) means the agent's tests don't count; a requirement the history can't support → refusal; Gemma's 0 findings on a PR with proven changes shows an AI "clean" is not evidence. Plus `FAILURE_MODES.md` (F-01…F-45).
   - *Who owns the decision?* The named human who signs (and, like Anthropic's rule, the person who prompted the agent counts as accountable). The AI never approves; bots can't fill a human slot.
   - *How would this scale?* Tiers: most PRs land T0/T1 (#2297: 237 → 9 files); compute replaces human minutes (CI cost per PR: give measured minutes from logs if available, else say "not measured"); trust ledger means calibration effort drops in regions with a track record and rises after escapes; Meta runs catching tests in production at scale (74 SEV privacy bugs at diff time, H1 2026) as an existence proof. Honest limit: needs a runnable sandbox per PR.

### P1 — strong differentiators, docs-only (≈1 h)
4. **Receipts by layer (frontend / backend / security / performance)** — the brief asks for all three; our sample is a backend library. A table in `03_CONCEPT.md`: for each layer, the *executed* receipt that replaces opinion, and what stays a human question.
   - Backend: catching tests base vs head; wire-format byte diff; consumer-compile check (our CS0579 find); public API diff (PublicAPI.*.txt / analyzer releases).
   - Frontend: visual snapshot diff base vs head (Argos/Playwright style), a11y scan delta, recorded user-flow trace; human question = "is this the intended look/flow?" (predict before seeing the screenshot).
   - Security: PR text quarantine (built), SAST **delta** base vs head (only new findings), secret scan (built for the site), authz tests as catching tests; always-human paths (auth, CI workflows, crypto).
   - Performance: benchmark base vs head with a noise band (run twice, like BeTell's noise filter); a regression outside the band is a behavior change.
   - "Generalist reviewer" = one router over layer-specific receipt makers; the LLM scopes and asks, it never certifies.
5. **Outcome metrics, not activity** — a short section: what the factory reports over time: escapes per region (trust ledger), reverts/incidents feeding the Time Machine (Anthropic's "incidents become evals", but judged by execution, not by LLM), placebo rate per agent (6/15), drill miss rate, catch rate per screener, human minutes per PR. Name revert rate as the guardrail metric.
6. **Prior-art positioning table** (from §1, condensed to 5 rows) in README and the concept card: "What exists / where it stops / what we add".
7. **Lead with the brief's own framing.** The brief's intro: "you are checking a story, and questioning the parts that do not add up". Our "agent's story vs the receipts" panel is exactly that: each claim stamped PROVEN / REFUTED / HEARSAY / REFUSED. Make it the first thing on the #2234 page and the first beat of the video.

### P2 — only if time remains
8. Zoom levels (overview → file → snippet) on the review page, citing 2606.01969. Probably already close; don't build new UI before the video.
9. Cite ADAPT/BeTell/JiTTests as the "Prove" lineage in `06_RESEARCH.md`.

### Don't
New LLM features, Nemotron, a frontend sample app, rerunning the pipeline, any claim without a source.
