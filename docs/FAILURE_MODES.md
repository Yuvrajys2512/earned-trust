# Failure modes

Deliverable (brief item 6): failure modes **we saw** in the agent's work and in AI review — plus known ones from research we design against. Mark each as `seen` (in our sample/run, with evidence) or `known` (from research).

| ID | Failure mode | Seen / known | Where / evidence | How the concept handles it |
| --- | --- | --- | --- | --- |
| F-01 | Fix targets a cause that isn't in the codebase's history | seen | #2234, commit `1a74a620` not ancestor of base | Scope stage checks requirement vs history |
| F-02 | Silent behavior change outside the requirement (duplicate keys dropped, mixed-key member skipped) | seen | #2234 `TypeCollector.cs` `ContainsKey` guards + `continue` | Catching tests prove it; tagged `collateral`; human asked |
| F-03 | Scope drift: global change for a local bug | seen | #2283 `ReportIfLocatedInCompilation` wraps all diagnostics | Requirement-scope tagging; question to human |
| F-04 | Volume hides the real change | seen | #2297: 222 of 237 files are regenerated snapshots | Regenerate + byte-compare → auto-clear |
| F-05 | No explanation from the agent | seen | All 4 branches: one-line commit messages | Reviewer builds intent blind |
| F-06 | Placebo tests (pass before and after) | seen | #2234: 4 of 8 new analyzer tests pass on base (L-03) | Tests must fail on base to count as evidence; tag per test, not per file |
| F-07 | Prompt injection via PR text / title / images | known | Azure DevOps hidden HTML comments; GhostCommit | Quarantine; story is untrusted |
| F-08 | Automation bias / rubber-stamping | known | GitHub trial; AIDev 98.2% no review comment | Predict-before-reveal |
| F-09 | Self-preference bias of same-family reviewer | known | Pombal et al. 2026 | Different family reviewer; author hidden |
| F-10 | Uncalibrated confidence numbers | known | Agent Trace `confidence: 0.95` with no calibration | Planted-bug catch rate per PR |
| F-11 | Flaky/irrelevant catching tests (false alarms) | known | Meta JiTTests paper | Filter: must pass on base deterministically (re-run) |
| F-12 | Reviewer over-claims from reading the diff (our own) | seen | We wrote "duplicate keys silently dropped"; executed tests show MsgPack005 error is reported (L-03) | Diff-reading claims are hearsay until a test proves them |
| F-13 | Wrong requirement, real fix: PR fixes a genuine bug that isn't the one in the issue | seen | #2234: fixes analyzer crash (AD0001) on duplicate/mixed keys, not the 3.1.1 suppression regression | Record links each proven change to the requirement separately; "real but unrequested" goes to the human |
| F-14 | Test names are story: name claims a topic its assertions don't test | seen | `SuppressSourceGenerationAnalyzerTests` catching tests are about duplicate keys | Judge tests by base/head outcome, never by name |
| F-15 | Toolchain pin silently disables code generation; whole test project can't compile | seen | `global.json` SDK 8.0.402 + Roslyn 4.12 generator → CS9057 warning (L-04) | Record toolchain per run; treat "didn't compile" as *unknown*, never *pass* |

Add rows as the build surfaces new ones (especially failures of *our own* reviewer).
