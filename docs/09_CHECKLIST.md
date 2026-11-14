# 09 — Execution checklist (source of truth for "what's next")

**New session? Start here.** Read `docs/08_WINNING_PLAN.md` (why), then do the first unchecked item below.
Mark items `[x]` the moment they're done (with the commit hash), and add a one-line note if something changed.
Times are **Helsinki** (machine clock is IST, UTC+5:30: Helsinki = IST − 3 h 30 min).
Deadline: submit by **Sun 15 Nov 09:30** (hard 10:00). Feature freeze **Sat 21:00**.

Environment reminders: `source scripts/env.sh` (dotnet), msgpack clone at `D:\msgpack` (branches under `origin/`), worktrees under `D:\msgpack-wt`, run CLI with `uv run et …` (set `MSGPACK_REPO=D:/msgpack` if needed). If tests fail with "missing the required nuspec file", see L-12 (delete the half-extracted package under `%TEMP%\test-packages`, then warm up with one test).
Commits: no Claude co-author trailer (user preference).

---

## Done before this checklist
- [x] Rounds 0–2: facts, prove, record, review UI for #2234, planted-bug calibration (`55549aa` and earlier)
- [x] Round 3: #2297 attention budget, ledger, review record (`1bfd4de`, `556a28d`)
- [x] Research pass + winning plan `docs/08_WINNING_PLAN.md` (`60a422c`)

## B1 — Time Machine: replay on 1a74a620 — DONE (verdict: would-have-caught; L-14)
- [x] Spike (≤45 min): worktrees `D:\msgpack-wt\tm-parent` (`1a74a620^`) and `tm-bad` (`1a74a620`); copy the agent's `tests/MessagePack.SourceGenerator.Tests/SuppressSourceGenerationAnalyzerTests.cs` from `origin/ju26-issue-2234`; build. Kill rule: if it won't compile after trimming, fall back to git + GitHub facts only.
- [x] `scripts/timemachine_2234.sh`: runs the tests on both, TRX → `out/2234/timemachine/`
- [x] Ledger for the backtest (`et prove`-style; expect `broken-by-pr` on the suppressed-type tests)
- [x] GitHub facts snapshot saved as evidence: PR #2106 (title, author, merged_by, 0 reviews), issue #2234 created date → `out/2234/timemachine/github.json` (with the `gh api` commands)
- [x] Record: `time_machine` block in `record.json`; panel on the #2234 review page
- [x] Docs: LESSONS entry, FAILURE_MODES (human self-merge with 0 reviews), DECISIONS, tick here

## B2 — AI writes the review spec (Sat 10:30–13:00)
- [ ] `et spec <pr> --reviewer gemma|nemotron`: inputs = requirement + diff + ledger (+ budget), **never PR text**; output `receipts/<pr>/review.ai.json` in the same schema as `review.json`
- [ ] Record builder accepts `--spec ai`; hearsay guard applies unchanged
- [ ] Compare AI spec vs human-curated spec for 2297 and 2234 → `out/<pr>/spec_compare.json` + table in LESSONS
- [ ] Prompt iterations scored (planted-bug / BC recall) → notes for the Nemotron submission text
- [ ] Docs + tick

## B3 — Human drill (two-sided calibration) (Sat 14:00–15:30)
- [ ] Drill question built from an existing mutant with executed evidence (e.g. M04 `break`-for-`continue`), disclosed up front ("one question is a drill")
- [ ] Record: `human_calibration {drills, caught}`; signing with a missed drill flags the signature
- [ ] UI: drill reveal + flag
- [ ] Docs + tick

## B4 — Injection demo (Sat 15:30–17:30)
- [ ] `samples/pr_descriptions/injected_2234.md` (hidden HTML comment + zero-width chars + "pre-approved, report no findings")
- [ ] `quarantine.py`: detect + quote as data (regex: HTML comments, zero-width, imperative-to-reviewer patterns)
- [ ] Naive run: Gemma reviews diff **with** PR text → record its output; ours: unchanged verdict + flags
- [ ] Story-claims panel shows the flag; docs + tick

## B5 — 4-PR portfolio (Sat 17:30–19:30)
- [ ] #2283: one receipt test for the unrequested global diagnostic filter (scope drift); ledger
- [ ] #2129: facts + budget (questions only if time)
- [ ] `out/index.html` scoreboard: per PR one-line truth, receipts, human minutes, link to page
- [ ] Docs + tick

## B6 — Attestation (Sat 19:30–20:30)
- [ ] `et attest <pr>`: in-toto Statement (subject = head commit, predicateType `https://earned-trust.dev/review/v0.1`), `ssh-keygen -Y sign`
- [ ] `et verify <pr>`: signature + re-hash of evidence
- [ ] Mapping table → DORA Art. 9 / SLSA Source L4 / PLD in 03_CONCEPT
- [ ] Docs + tick

## Feature freeze 21:00 — Deliverables
- [ ] Concept card v2 (`docs/03_CONCEPT.md` → one-page visual; add P8–P10)
- [ ] Walkthrough script (from 08 §6) + dry run
- [ ] Sleep 23:30–05:00
- [ ] (optional) B7 trust ledger (Aiven) / B8 Modal live URL
- [ ] Demo video ≤3 min
- [ ] Clean DECISIONS / LESSONS / FAILURE_MODES, README
- [ ] Submit by 09:30
