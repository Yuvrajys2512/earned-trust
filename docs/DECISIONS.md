# Decision log

Format: newest first. One line of decision, one line of why. Times Helsinki.

| When | Decision | Why |
| --- | --- | --- |
| Sat 14 Nov ~10:05 | Budget minutes are an **estimate** (changed lines ÷ 20/min, ≥0.5 min/file) and the page says so; human files are ordered src → templates → tests → docs; anything over budget is shown as *knowingly unread*, never hidden | A budget the human can't see the edges of is a hidden auto-approve. The rate is a stated assumption, not a measurement |
| Sat 14 Nov ~10:00 | T4 outputs are cleared by a string-level check (added template lines vs decoded `this.Write` literals), labelled as such, not a T4 re-run | T4 "preprocessed" templates need Visual Studio; the string check is executed and catches a hand-edited or stale `.cs`, and the snapshots (byte-identical) already prove the end-to-end output |
| Sat 14 Nov ~09:40 | Snapshots are cleared by **reset to base → regenerate with head generator → git blob compare**, not by regenerating over the PR's files | Regenerating over the PR's own bytes can't tell "regenerated identical" from "never rewritten". Starting from base bytes, an unrewritten file shows as `not-regenerated` and stays with the human |
| Sat 14 Nov ~07:20 | Record builder **fails closed**: a behavior change is `proven` only if every cited test is in the ledger and `catching`; story claims marked "true but not new" are re-checked (cited tests must be placebos) | The spec is claims; only the ledger is receipts. Caught our own bug in L-06 |
| Sat 14 Nov ~07:15 | Review UI is one self-contained HTML file with the record embedded; prediction is SHA-256-committed (id, choice, time) before the reveal; Sign is locked until every BC is predicted + decided and residual risk + name are filled | Works offline, deployable anywhere (Modal later); commit-before-reveal makes P5 checkable, not a promise |
| Sat 14 Nov ~07:05 | Reviewer-written catching tests live in `receipts/<pr>/` and are injected into both worktrees; the generator test writes its output to `$ET_EVIDENCE_DIR` so the reveal shows real generated code | Reviewer ≠ author tests (F-16); the reveal shows the actual artifact, not a description |
| Sat 14 Nov ~07:05 | v0 reviewer spec (`receipts/2234/review.json`) is human-curated and labelled so; a model generates it in Round 2 | Get the end-to-end flow demoable first; the spec format is the contract the model must fill |
| Sat 14 Nov ~07:30 | Concept name: **Receipts, not reviews** (pipeline tagline: *Prove · Predict · Sign*) | Says the core idea in three words: executed evidence instead of opinions. The 2234 placebo-test finding (6/10 tests have no receipt) shows it on real data |
| Sat 14 Nov ~06:30 | `git_facts` classifies T4 outputs by checking a sibling `.tt` exists in the head tree, not by folder | First version put `TransformUtilities.cs` (hand-written, in `Transforms/`) in the auto-clearable bucket — exactly the file a human must see |
| Sat 14 Nov ~06:30 | Regression archaeology is generic: requirement may carry `regressed_between=(good, bad)`; we check ancestry of `bad` and of every `good..bad` commit touching the PR's src files | Turns the one-off 2234 finding into a reusable Scope-stage check with executed evidence |
| Sat 14 Nov ~06:15 | Stack: Python orchestrator (`src/earned_trust`, `uv run et …`), stdlib only for now; `dotnet` CLI for builds/tests; bash scripts for one-off checks | Zero install friction; add deps (LLM SDKs) only when a stage needs them |
| Sat 14 Nov ~06:00 | Clone the challenge repo read-only from upstream to `D:\msgpack`; no GitHub fork | We never push to it — catching tests and mutants live in local `git worktree`s under `D:\msgpack-wt`. Fork only if a partner tool (e.g. Modal) needs a URL |
| Sat 14 Nov ~06:00 | .NET SDK 8.0.428 installed user-locally (`%LOCALAPPDATA%\Microsoft\dotnet`), loaded via `scripts/env.sh` | No admin needed; satisfies `global.json` 8.0.402 + rollForward patch |
| Sat 14 Nov ~02:00 | Set up repo with shared agent context (AGENTS.md + CLAUDE.md import) | Claude Code and Codex both work from the same source of truth |
| Sat 14 Nov ~02:00 | Iterate in rounds; each round must end demoable | Solo team, ~32 h left; protects against running out of time |
| Sat 14 Nov ~01:30 | Concept spine: AI proves behavior changes, human predicts before reveal, mismatches are the review | Research shows no tool answers brief items 4 and 5 (refusals, sign-off without full read) |
| Sat 14 Nov ~01:30 | Main demo PR: `ju26-issue-2234` | Small (4 files), has a requirement ID, and contains a hidden behavior change + a regression-history oddity |
| Sat 14 Nov ~01:00 | Also allowed to work on multiple challenges; Earned Trust is primary, Blueprints secondary and dropped if behind at Sat 18:00 | Concept-weighted judging and 25 vs 70 teams favour this track for a solo builder |
| Sat 14 Nov ~00:45 | Switched main challenge from "Make Blueprints Talk" to "Earned Trust in AI Code" | Fewer teams; concept > code; links to TrustGuard (inter-agent trust) work |
| Fri 13 Nov | Compete solo (one-person team) | Full control over scope and decisions |
