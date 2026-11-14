# 02 — Sample data: the four agent-written branches

All four branches sit on the same base commit **`32258fdb`** ("Bump PolySharp from 1.14.1 to 1.15.0", 1 Mar 2025, `develop` lineage; `git describe` output depends on which tags you fetched — e.g. `v3.0.238-rc.1-66-g32258fdb`, or `v.1.7.3.6-2870-g32258fdb` on a plain clone). Each branch is a single commit by "Stelian Vultur <stelian.vultur@tieto.com>", dated 12 Nov 2026.

**Commit messages are one line. No agent explanation exists.** Whatever "story" the human sees, our system has to build and verify itself.

| Branch | Head | Files | `.g.cs` snapshots | Issue |
| --- | --- | --- | --- | --- |
| `ju26-issue-2234` | `9007cee1` | 4 | 0 | [#2234](https://github.com/MessagePack-CSharp/MessagePack-CSharp/issues/2234) |
| `ju26-issue-2283` | `9df83c38` | 4 | 0 | [#2283](https://github.com/MessagePack-CSharp/MessagePack-CSharp/issues/2283) |
| `ju26-issue-2129` | `083afd99` | 28 | 0 | [#2129](https://github.com/MessagePack-CSharp/MessagePack-CSharp/issues/2129) |
| `ju26-issue-2297` | `a0aa5ab2` | 237 | 222 | [#2297](https://github.com/MessagePack-CSharp/MessagePack-CSharp/issues/2297) |

The size ladder (4, 4, 28, 237) looks deliberate: it breaks any one-size-fits-all review process.

---

## #2234 — Analyzer doesn't work when `SuppressSourceGeneration = true` (MAIN DEMO)

**Requirement (issue):** reporter says the analyzer stopped working in **3.1.1**; **3.1.0** still worked. No repro steps, no maintainer comments.

**What the agent changed** (`src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs`, +22/−4, plus README, 2 new test files):
- After reporting `DoNotMixStringAndIntKeys`, adds `continue;` → the mismatched member is **skipped** (two places, ~L1005 and ~L1138).
- Wraps `intMembers.Add(...)` / `stringMembers.Add(...)` in `if (!ContainsKey(...))` → on a **duplicate key the first member wins, the second is silently dropped** (four places).
- New tests: `tests/MessagePack.SourceGenerator.Tests/SuppressSourceGenerationAnalyzerTests.cs` (193 lines: MsgPack004, MsgPack015, … reported for suppressed types) and `tests/MessagePack.SourceGenerator.ExecutionTests/SuppressedSourceGenerationTests.cs`.

**Our finding (verified with git, 14 Nov):**
- The regression between v3.1.0 and v3.1.1 traces to commit **`1a74a620`** "stop collect field when object marked SuppressSourceGeneration" (neuecc, 25 Dec 2024). It moved `if (suppressSourceGeneration is true) return null;` from the **end** of `GetObjectInfo` to the **start** (~L714), so member analysis — and therefore analyzer diagnostics — never ran for suppressed types. That matches the bug report exactly.
- **`1a74a620`, `v3.1.0` and `v3.1.1` are NOT ancestors of the challenge base `32258fdb`.** In the base, the early return is still at the end (~L1369), so analysis does run for suppressed types.
- So the reported root cause does not exist in the code the agent worked on. The agent instead changed duplicate-key / mixed-key handling — a **behavior change not asked for by the requirement**.

**Verified 14 Nov (`scripts/verify_2234_base.sh`, see LESSONS_LOG L-03):** of the agent's 8 analyzer tests, **4 pass on base (placebos)** and **4 fail on base / pass on head**. The 4 real ones show that on base the analyzer reports MsgPack005 and then **crashes with AD0001** on duplicate or mixed keys; the PR removes the crash. So the PR fixes a real analyzer bug — just not the #2234 regression. Correction to our earlier reading: the duplicate-key drop is *not* silent by default, because MsgPack005 is an error.

Reproduce the git facts:
```bash
git log --oneline v3.1.0..v3.1.1 -- src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs
git show 1a74a620 -- src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs
git merge-base --is-ancestor 1a74a620 32258fdb && echo ancestor || echo NOT-ancestor
git show 32258fdb:src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs | grep -n 'suppressSourceGeneration is true'
```

**Questions the human should be asked (predict-then-reveal candidates):**
- "A `[MessagePackObject]` type has two members with `[Key(0)]`. What should the generator/analyzer do?" (PR: silently keeps the first, drops the second, plus whatever diagnostic is reported.)
- "One member uses an int key, the rest use string keys. Should that member be serialized?" (PR: skipped via `continue`.)
- "Does this PR fix the 3.1.1 regression described in #2234?" (Evidence: the regression commit isn't in this history.)

---

## #2283 — `IndexOutOfRangeException` for closed generic value type from a referenced assembly

**Requirement:** generator (CS8785) and analyzer (AD0001) crash when a `[MessagePackObject]` member's type is a closed generic **value type** (`record struct Item<T>` / `struct Item<T>`) defined in a referenced assembly. Cause pointed at `DeclaringSyntaxReferences[0]` on metadata symbols (empty collection). Reporter didn't know which of three indexing sites fails.

**What the agent changed** (`TypeCollector.cs` +26/−3, README, `doc/analyzers/MsgPack004.md`, `GenericsFormatterTests.cs` +189):
- Fixed both live `[0]` sites (BothStringAndIntKeyAreNull via new `GetPropertyIdentifierLocation`; MemberNeedsKey via `FirstOrDefault()`). The third `[0]` site (~L715) is commented-out code. ✅ requirement met.
- **Also** wrapped the whole `reportDiagnostic` callback in `ReportIfLocatedInCompilation`, which drops **every** diagnostic whose location isn't in source of the current compilation. ⚠️ Global change for a local crash. Suspicion to test: diagnostics created with a null/`Location.None` location for types *in* the current project are now silently dropped.

**Predict-then-reveal candidate:** "A type in *your own* project triggers a diagnostic whose location can't be resolved. Should you still see the warning?"

---

## #2129 — Generate a formatter for a type in a referenced assembly (feature)

28 files: new attribute in `MessagePack.Annotations/Attributes.cs`, `GeneratedFormatterCollector.cs`, `GeneratedFormatterRequest.cs`, new analyzers **MsgPack019–MsgPack022** (+ docs, `AnalyzerReleases.Unshipped.md`), template changes, a new test project `MessagePack.SourceGenerator.ExternalTypes` with `ExternalPerson/Point/Widget`, execution tests. Good candidate to show **public API surface change** → always a human decision (refusal category).

---

## #2297 — Add `[ExcludeFromCodeCoverage]` to generated code

237 files, of which **222 are regenerated `.g.cs` snapshot files** under `tests/MessagePack.SourceGenerator.Tests/Resources/**`. The 15 hand-edited files: README, 6 T4 templates (`*.tt`) and their generated `*.cs` counterparts in `src/MessagePack.SourceGenerator/Transforms/` (Composite resolver, Enum, Formatter, Resolver, StringKey formatter, Union), `TransformUtilities.cs`, and `tests/.../CodeCoverageExclusionTests.cs`.

**Attention-budget demo:** regenerate the snapshots from the templates; if byte-identical to the PR's `.g.cs`, auto-clear all 222. The human looks at the templates (6 × 3–9 lines) and one test. Also check: are the `.cs` template outputs consistent with their `.tt` sources?

---

## Useful commands

```bash
git clone https://github.com/<you>/junction26-messagepack-csharp msgpack && cd msgpack
git fetch origin 'refs/heads/ju26-*:refs/remotes/origin/ju26-*' --tags
for b in 2234 2283 2129 2297; do git diff --stat origin/ju26-issue-$b~1 origin/ju26-issue-$b | tail -1; done
git diff origin/ju26-issue-2234~1 origin/ju26-issue-2234 -- '*TypeCollector.cs'
```
