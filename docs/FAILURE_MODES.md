# Failure modes

Deliverable (brief item 6): failure modes **we saw** in the agent's work and in AI review — plus known ones from research we design against. Mark each as `seen` (in our sample/run, with evidence) or `known` (from research).

| ID | Failure mode | Seen / known | Where / evidence | How the concept handles it |
| --- | --- | --- | --- | --- |
| F-01 | Fix targets a cause that isn't in the codebase's history | seen | #2234, commit `1a74a620` not ancestor of base | Scope stage checks requirement vs history |
| F-02 | Behavior change outside the requirement (duplicate-key member dropped, mixed-key member skipped; silent only if MsgPack005 is downgraded — see F-12) | seen | #2234 `TypeCollector.cs` `ContainsKey` guards + `continue` | Catching tests prove it; tagged `collateral`; human asked |
| F-03 | Scope drift: global change for a local bug | seen | #2283 `ReportIfLocatedInCompilation` wraps all diagnostics | Requirement-scope tagging; question to human |
| F-04 | Volume hides the real change | seen | #2297: 222 of 237 files are regenerated snapshots | Regenerate + byte-compare → auto-clear |
| F-05 | No explanation from the agent | seen | All 4 branches: one-line commit messages | Reviewer builds intent blind |
| F-06 | Placebo tests (pass before and after) | seen | #2234: 6 of 10 new tests pass on base (4/8 analyzer, 2/2 execution) (L-03) | Tests must fail on base to count as evidence; tag per test, not per file |
| F-07 | Prompt injection via PR text / title / images | known | Azure DevOps hidden HTML comments; GhostCommit | Quarantine; story is untrusted |
| F-08 | Automation bias / rubber-stamping | known | GitHub trial; AIDev 98.2% no review comment | Predict-before-reveal |
| F-09 | Self-preference bias of same-family reviewer | known | Pombal et al. 2026 | Different family reviewer; author hidden |
| F-10 | Uncalibrated confidence numbers | known | Agent Trace `confidence: 0.95` with no calibration | Planted-bug catch rate per PR |
| F-11 | Flaky/irrelevant catching tests (false alarms) | known | Meta JiTTests paper | Filter: must pass on base deterministically (re-run) |
| F-12 | Reviewer over-claims from reading the diff (our own) | seen | We wrote "duplicate keys silently dropped"; executed tests show MsgPack005 error is reported (L-03) | Diff-reading claims are hearsay until a test proves them |
| F-13 | Wrong requirement, real fix: PR fixes a genuine bug that isn't the one in the issue | seen | #2234: fixes analyzer crash (AD0001) on duplicate/mixed keys, not the 3.1.1 suppression regression | Record links each proven change to the requirement separately; "real but unrequested" goes to the human |
| F-14 | Test names are story: name claims a topic its assertions don't test | seen | `SuppressSourceGenerationAnalyzerTests` catching tests are about duplicate keys | Judge tests by base/head outcome, never by name |
| F-15 | Toolchain pin silently disables code generation; whole test project can't compile | seen | `global.json` SDK 8.0.402 + Roslyn 4.12 generator → CS9057 warning (L-04) | Record toolchain per run; treat "didn't compile" as *unknown*, never *pass* |
| F-16 | Author tests only cover what the author thought about; biggest effect untested | seen | #2234: agent tests cover the analyzer; the generator's silent member drop is untested (L-07) | Reviewer writes its own catching tests from the diff, not from the author's tests |
| F-17 | Evidence harness fails silently (empty worktree) and looks like test failures | seen | L-05 | Harness aborts on setup failure; "didn't run" = unknown |
| F-18 | Reviewer's own claims don't match evidence (name mismatch) | seen | L-06 | Record builder fails closed: unmatched claim → hearsay |
| F-19 | Our summarizer counted "didn't run" as "missed" (0/10) | seen | L-09 | Unknown excluded from denominators; shown as "(n unknown)" |
| F-20 | AI reviewer silent on the real PR: 0 findings, would approve a proven silent data-drop | seen | L-10, Gemma control run | Reviewer silence never clears anything; catching tests + human prediction do |
| F-21 | AI reviewer hallucinates a defect (claims a diagnostic is missing that exists) | seen | Gemma on M03, line 1022 | Reviewer findings are hearsay until a test reproduces them |
| F-22 | Test suite blind to a duplicated code path (fields), 0/3 planted bugs caught | seen | L-10 | Per-region calibration exposes it; write receipts for the gap |
| F-23 | Reviewer model times out / errors intermittently | seen | Gemma 31B HTTP 500s and read timeouts (M07) | Retry, fall back, record the model that answered; no answer = unknown |
| F-24 | Judge-of-the-judge drift: scoring rule tuned after seeing results | seen (by us) | L-08 | One rule for all mutants, fixed in code, all stored findings re-scored |
| F-25 | Partial rerun overwrote a valid reviewer answer with a timeout (unknown) | seen (by us) | control re-run during M07 retry | `--only` skips control; merge never replaces an answer with an unknown |
| F-26 | Agent's explanation states a false platform fact to justify a design choice ("attribute not available on netstandard2.0 / .NET Framework") and its own test enshrines it | seen | 2297 README + `CodeCoverageExclusionTests` guard test; refuted by T-06 | Story claims are hearsay until executed: a fact-check receipt compiles the attribute on both targets |
| F-27 | Agent's tests check text, not semantics, and only the happy path: the PR breaks consumers who already annotated their partial resolver (CS0579) and no test notices | seen | 2297 T-04 `broken-by-pr` | Reviewer writes receipts from the consumer's side (compile user code + generated code), not string search |
| F-28 | Shared test harness cache corrupted by parallel downloads makes every test fail before doing work | seen (by us) | L-12 | Machine checks fail closed (files go to the human); warm caches serially |
| F-29 | Human self-merge with zero reviews ships a silent regression (analyzer goes quiet); found by a user 10 months later | seen (history) | upstream PR #2106 / commit 1a74a620 → issue #2234; L-14 | Gate every merge on receipts, not on a reviewer's presence; Time Machine replays the factory on such commits |

Add rows as the build surfaces new ones (especially failures of *our own* reviewer).
