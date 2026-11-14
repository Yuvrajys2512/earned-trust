# 06 — Research: what exists and the gap

Full write-up with sources: https://claude.ai/artifact/CLkQN8uG9THpNLXeBSgNku (Earned Trust in AI Code — Landscape & Wow Ideas)

## One-line summary
Every AI reviewer on the market answers *"what's wrong with this diff?"*. The brief asks *"what lets a named human sign it without reading it?"*. Nobody answers that yet.

## Existing tools (as of Nov 2026)
- **Claude Code Review** — parallel agents + a verification step that filters false positives; <1% findings marked wrong; $15–25/review.
- **Ito** — builds the app per PR, runs affected flows, posts runtime evidence (video, logs, repro).
- **Greptile** — repo-wide context; claims 82% catch on its own 50-bug benchmark.
- **CodeRabbit, GitHub Copilot review, Cursor Bugbot, Qodo, Graphite** — summaries + line comments; benchmarks are mostly vendor-run.
- **GitHub ReviewBench** (Oct 2026) — 219 PRs; scores finding recall/noise, not sign-off.
- **Agent Trace** (Cursor spec) — which lines came from which model; explicitly no quality judgment.

## Research to cite
- **Meta JiTTests** — tests generated per diff that pass on parent and fail on the diff; ~4x more catches than ordinary test generation (22,126 tests); 74 privacy incidents caught at diff time in H1 2026. Closest prior art for our "prove" step.
- **Meta ACH / Assured LLM-based SE** — LLM output only counts with assurances (builds, passes, kills a mutant).
- **Meta Diff Risk Score** — LLM predicts which diffs cause incidents; used to unfreeze code freezes.
- **AIDev studies** — 98.2% of Codex PRs had no recorded review comment; peripheral devs merge agent PRs without running checks more often.
- **Automation bias** — reviewers approve AI-assisted code more readily; fix = cognitive forcing (make the human commit to something before approving).
- **Self-preference bias** — judges can be up to 50% more likely to pass failing outputs from their own model family.
- **Prompt injection via PR text** — Azure DevOps hidden HTML comments, Claude Code Security Review PR-title attack, GhostCommit (PNG) passing CodeRabbit + Bugbot.
- **Threat Image Projection (airports)** — fake threat images projected onto 1–4% of real bags to measure screeners on the job. Our analogy for measuring the AI reviewer.
- **Proof-carrying code (Necula, 1997)** — code ships with a proof the receiver checks cheaply.

## The gap (maps to brief expectations)
| Brief expects | Status today |
| --- | --- |
| 4. What the AI refused to decide | Nobody reports refusals |
| 5. Named human accepts without a full read | Evidence exists (Ito, Claude), sign-off doesn't |
| 2. Calibrated confidence | Self-reported or vendor benchmarks only |
| 3. Review tied to requirement ID | Spec Kit traces at authoring time, not review time |
| 6. Reviewer's own failure modes | Self-graded benchmarks |
