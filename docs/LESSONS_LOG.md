# Lessons log

Deliverable. Log every surprise, dead end and insight as it happens — short, dated, honest. Newest first.

Template:
```
### L-NN — <title> (<time>)
What happened:
What we learned:
What changed in the concept/build:
Evidence: <command / file / link>
```

---

### L-07 — Our own receipts prove the change the agent never mentioned (Sat 14 Nov ~08:30)
What happened: we wrote 4 reviewer-side catching tests (`receipts/2234/EtGeneratorReceiptsTests.cs`) that run the *source generator* (not the analyzer) on duplicate/mixed keys and save its output. All 4 fail on base and pass on head. On base the generator throws (`ArgumentException … Key: 0`, `InvalidOperationException: Nullable object must have a value`). On head it emits a formatter that writes and reads only `First`; `Second` is gone from both `Serialize` and `Deserialize`.
What we learned: the agent's tests only cover the analyzer. The PR's biggest user-visible effect — a generated formatter that silently drops a member when MsgPack005 is downgraded — has no test, no README line and no commit text. Only reviewer-written tests found it.
What changed: BC-2 ("first duplicate wins, silently") becomes the headline predict-then-reveal question. The reviewer must write its own tests; the author's tests describe what the author *thought* about.
Evidence: `out/2234/verify/evidence/{base,head}/dup-int.txt`; `uv run et prove 2234`.

### L-06 — The hearsay guard caught *our* spec (Sat 14 Nov ~08:20)
What happened: the first `et record` marked BC-2 and BC-3 as "unproven · hearsay" although the tests had passed. Cause: xUnit/TRX names our tests with their namespace, so the spec's test names didn't match ledger entries. The record builder refuses to mark a change proven unless every cited test is found *and* catching.
What we learned: the rule "a claim without a matching receipt is hearsay" applies to the reviewer's own claims too, and it works — it failed closed, not open.
What changed: `prove.short_name` normalizes test names to `Class.Method`.
Evidence: first run output `3 behavior changes (1 proven), 2 refusals, 2 hearsay`.

### L-05 — The evidence harness can silently run on an empty tree (Sat 14 Nov ~08:00)
What happened: on rerun, `git worktree remove --force` unregistered the worktrees but Windows file locks (MSBuild / build-server nodes) left files behind; `git worktree add` then failed, the script carried on, and `dotnet test` ran in a directory with only our injected files → NuGet restore errors on both sides.
What we learned: a harness failure looks like "tests failed on both sides". Because "didn't run" maps to *unknown* (F-15), no false catching test was produced — but a naive base-fail/head-pass reader could have been fooled if only one side broke.
What changed: `fresh_worktree` shuts down build servers, deletes leftovers, prunes, and aborts if `worktree add` fails.
Evidence: `out/verify_2234_run.log` (first rerun): `fatal: 'D:/msgpack-wt/2234-head' already exists`.

### L-04 — The repo's own toolchain pin silently disables its source generator (Sat 14 Nov ~07:00)
What happened: `global.json` pins SDK 8.0.402 (Roslyn 4.11), but the generator is compiled against Roslyn 4.12. Under the pinned SDK the compiler skips the generator with **warning** CS9057, so `MessagePack.SourceGenerator.ExecutionTests` fails to compile (CS0117 `GeneratedMessagePackResolver.Instance` missing) on base *and* every PR — including pre-existing tests.
What we learned: "CI is green" depends on which SDK CI really uses; a warning can turn a whole test project into dead weight. Evidence must record the toolchain it ran on.
What changed: our worktrees override `global.json` to SDK 9.0.x (local only, never pushed). The review record should carry `toolchain: {sdk, roslyn}` per run.
Evidence: `out/2234/verify/*ExecutionTests.log` → `CS9057 … references version '4.12.0.0' of the compiler, which is newer than the currently running version '4.11.0.0'`.

### L-03 — 6 of the agent's 10 tests are placebos; the other 4 prove a *different* fix (Sat 14 Nov ~06:50)
What happened: ran the agent's 10 new tests (8 analyzer tests in `SuppressSourceGenerationAnalyzerTests`, 2 execution tests in `SuppressedSourceGenerationTests`) on base `32258fdb` with only the test files copied in, then on the PR head. Execution tests needed SDK 9 to compile (L-04); analyzer results were identical on SDK 8 and 9.
- **Both execution tests pass on base** (placebo): `SuppressedTypeRoundTripsThroughDynamicResolver`, `NoFormatterIsGeneratedForSuppressedType`.
- **4 pass on base** (placebo for this PR): `SourceGenerationOnlyDiagnosticsAreNotReportedWhenSuppressed`, `MemberTypeMustBeMessagePackObjectIsReported`, `MemberWithoutKeyIsReported`, `AllowPrivateRequiredIsReported`. They show analyzer diagnostics *already* fire for suppressed types on base — executed confirmation of L-01 (the #2234 regression isn't in this history).
- **4 fail on base, pass on head** (real catching tests): duplicate int keys, duplicate string keys, mixed int/string keys, duplicate keys on generated types. On base the analyzer reports MsgPack005 and then **crashes** (AD0001: `ArgumentException: An item with the same key has already been added` / `InvalidOperationException: Nullable object must have a value`). On head: MsgPack005 only, no crash.
What we learned:
1. The agent *did* fix a real "analyzer stops working" bug — an analyzer crash on invalid keys — just not the one the issue describes. "Wrong requirement, real fix" is a distinct outcome from "wrong fix"; the record needs to say both.
2. Our own earlier claim ("duplicate-key members are *silently* dropped") was hearsay from reading the diff. Executed: MsgPack005 is an **error**, so the user is told. The drop is only silent if a project downgrades MsgPack005's severity — a much narrower question for the human.
3. A test's *name* is story too: the class is called `SuppressSourceGeneration…` but its catching tests are about duplicate keys.
What changed: the predict-then-reveal question for 2234 becomes "if MsgPack005 is suppressed, should the generator keep the first member, drop both, or fail?". The ledger must tag each test individually (placebo / catching), never per file.
Evidence: `bash scripts/verify_2234_base.sh` → `out/2234/verify/base-MessagePack.SourceGenerator.Tests.log` (Passed 4 / Failed 4), `base-…ExecutionTests.log` (Passed 2), `head-*.log` (all pass).

### L-01 — The 2234 fix targets a bug that isn't in this code's history (Sat 14 Nov ~01:40)
What happened: Issue #2234 says the analyzer broke in v3.1.1 (worked in v3.1.0). The breaking commit `1a74a620` moved the `SuppressSourceGeneration` early return to the top of `GetObjectInfo`. That commit, v3.1.0 and v3.1.1 are not ancestors of the challenge base `32258fdb`, where the return is still at the end. The agent changed duplicate-key/mixed-key handling instead.
What we learned: An AI reviewer that only reads the diff + the issue would happily approve this ("tests added, issue referenced"). Checking the requirement against the code's actual history is cheap and decisive.
What changed: "Root-cause archaeology" becomes a step in the Scope stage; 2234 becomes the main demo.
Evidence: see docs/02_SAMPLE_DATA.md (#2234 commands).
Open: run the agent's new tests on base (`scripts/verify_2234_base.sh`) — if they pass there, they are placebo tests.

### L-02 — Agent commits carry no explanation (Sat 14 Nov ~01:20)
What happened: All four branches have one-line commit messages; no PR description.
What we learned: The brief imagines a PR that "opens with its own explanation". In reality the reviewer must build the story — and must not trust one if given.
What changed: Principle P4 (story is untrusted input; derive intent blind).
