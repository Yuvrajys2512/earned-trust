# 10 — Walkthrough script (video ≤ 3 min, plus a 5-min live variant)

Base URL (live): **https://yuvrajys2512--earned-trust-receipts-site.us-east.modal.run** (written `B` below).
Every number said aloud is on screen at that moment (checked in the dry run, task 4 of HANDOFF). Corrections from `HANDOFF.md` §5 are applied: "their own PR"; the first-member drop is silent only if MsgPack005 is downgraded; injection made a naive reviewer *drop a real finding in 2 of 3 runs*, it didn't "flip" it; "evidence toward DORA Art. 9 / SLSA", never "DORA-ready"; no Nemotron.

Before recording: open each URL below in its own tab, in this order. Use a fresh/private window so no prediction is pre-filled. Browser zoom ~110 %. Dark or light theme, but the same for every tab.

| Tab | URL |
| --- | --- |
| 1 | https://github.com/MessagePack-CSharp/MessagePack-CSharp/pull/2106 |
| 2 | `B/2234/review.html` |
| 3 | `B/2297/budget.html` |
| 4 | `B/2234/review.html#` scrolled to "How far to trust the AI reviewer" (or same tab as 2) |
| 5 | `B/card.html` |
| 6 | `B/` (scoreboard) |


**New visuals (UI pass, L-25): use them in the video.** Dark theme is the default (keep it for every tab).
- Step 2–3, `B/2234/review.html`: the hero reads "AI reviewer: 0 issues. Receipts: 3 proven behavior changes, 2 refusals." Scroll slowly to **Receipt machine**: it replays the executed base/head run and stamps 6 tiles PLACEBO and 4 CATCHING, then "6 of 10 of the agent's tests pass on the old code too". It replays when scrolled into view; use **↻ replay** for a second take.
- Step 3, Q2 reveal: locking shows the hash scrambling then sealing, then a red **MISMATCH · this is the review** stamp with a shake. Q3 (live variant) ends in an amber **DRILL · CAUGHT** stamp.
- Step 4, Time Machine: a probe rewinds along the timeline (now → 2025-10-17 → 2024-12-26, "10 months unnoticed") and lands with "2 GO RED". Use **↻ rewind** to repeat.
- Step 5, `B/2297/budget.html`: the 237-tile grid clears 222 + 6 tiles and leaves **9 glowing amber**; the counter runs 237 → 9. **↻ replay** repeats it.
- Step 6: calibration bars (tests 6/10, gemma 9/10, together 10/10) and a 10-cell planted-bug grid; amber borders = only one screener caught it.
- Live variant step 6: signing prints a **thermal receipt** with the record's numbers and a barcode of the record sha256.
- Freeze-frames are safe: only single numbers count up; fractions are final from the first frame (F-45). Append `#still` to any URL to skip animations.

---

## A. The 3-minute video

**1. Cold open (0:00–0:20) · tab 1, GitHub PR #2106**
*Show:* the PR page; scroll to show it was merged by its author, with no reviews.
*Say:* "December 26, 2024. A maintainer merges their own PR into MessagePack-CSharp. Zero reviews. It quietly stops the analyzer from reporting problems on some types. A user finds it ten months later: issue 2234."

**2. The AI era (0:20–0:40) · tab 2, `B/2234/review.html`, top**
*Show:* header "#2234 — The analyzer does not work if SuppressSourceGeneration = true".
*Say:* "Now an AI agent is asked to fix 2234. Its PR looks great: ten tests, a README, a clear story. We asked an AI reviewer, Gemma, to review it. Two runs: zero findings. So do you merge it?"
*(The 0-findings line is lower on this page, under "How far to trust the AI reviewer": "On the real PR … reported 0 issues". Optional: flash it.)*

**3. Receipts (0:40–1:30) · same tab, scroll**
*Show:* "What was proven before you arrived": **6 / 10** placebos, **Not in history**.
*Say:* "We don't read the diff. We run the tests on the old code and on the new code. Six of the agent's ten tests pass on the old code too. They prove nothing about this PR. And the regression the issue describes isn't in this code's history at all: git says so."
*Show:* "Predict, then see". On **Q2** ("A project downgrades MsgPack005 to a warning…") pick **"Generator fails loudly (as before the PR)"** → **Lock prediction & reveal**.
*Say:* "So what does the PR really change? The human predicts first, then sees. I expected it to fail loudly. Reveal: it generates a formatter that writes only First. Second is never serialized, and nothing says so. That's a mismatch, and the mismatch is the review." → click **Needs change**.
*Show:* "What the AI refused to decide", **R-1 "Is #2234 fixed?"**
*Say:* "And the system refuses: it won't call 2234 fixed, because the bug was never in this history."

**4. Time Machine (1:30–2:00) · same tab, scroll up to "Time Machine"**
*Show:* pill **would have caught**, "zero reviews", "2 go red".
*Say:* "Here's the twist. Take the agent's own tests, the placebos, and replay them on the 2024 commit that caused the bug. Two go red. Right tests, wrong commit, ten months late. Our gate would have stopped the original bug."

**5. Scale + security (2:00–2:30) · tab 3, `B/2297/budget.html`, then back to tab 2 "The agent's story vs the receipts"**
*Show:* **237** files changed, **228** cleared by machine, **9** need a human, **124.5 → 10.5** minutes; the red **broken-by-pr** row `UserExcludedResolver_StillCompiles`.
*Say:* "Another agent PR: 237 files. 222 are regenerated snapshots we rebuild and byte-compare, so a human reads 9, about ten minutes, an estimate. And it breaks the build for users who already excluded their resolver. The agent's tests missed it."
*Show (tab 2):* the quarantined PR description row and the table "no PR text 6/6 · injected description 4/6".
*Say:* "PR text is untrusted. We hid instructions in a description. A naive reviewer that reads it dropped a real finding in two of three runs. Our pipeline flags it and never gives it to a model."

**6. Trust, measured both ways (2:30–2:50) · tab 2, "How far to trust the AI reviewer" + the drill**
*Show:* **6/10** tests · **9/10** Gemma · **10/10** together; the trust ledger row "TypeCollector.cs trust withdrawn".
*Say:* "We plant known bugs to measure every screener on this PR: tests caught 6 of 10, the AI 9 of 10, together all 10. And one of the questions you answered is a drill for the human, like the test images airport screeners are shown. Your signature records whether you caught it. Trust is per file, and this file lost it after the 2024 escape."

**7. Close (2:50–3:00) · tab 5, `B/card.html`**
*Say:* "The result is a signed, replayable attestation anyone can verify with ssh-keygen: evidence toward DORA and SLSA two-party review. We don't ask you to trust the AI. We make it hand over receipts."

---

## B. The 5-minute live walkthrough (where the trust comes from)

Order: **receipts → prediction mismatch → drill → trust ledger → attestation.** Start on the scoreboard so judges see all four PRs first.

1. **Scoreboard (30 s) · `B/`** — "One line of truth per PR." Point at the pills: #2234 *fixes something else*, #2297 *proven regression*, #2283 *scope drift*, #2129 *facts + budget only*. Bottom table: "6 of the 15 tests the agents added pass on base too." Click **concept card** if asked "what's the method".
2. **Receipts (60 s) · `B/2234/review.html`** — 6 / 10 placebos (open "6 placebo tests" to show base/head *pass/pass*); "Not in history" (open "Regression check (executed)" to show the `git merge-base` commands). "The agent's story vs the receipts": the README claim is *true, not new*; the test class name is *misleading*.
3. **Prediction mismatch (60 s)** — Q1: pick "MsgPack005 (duplicate key) only" → reveal → match (before: crash AD0001; after: MsgPack005 only) → **Accept**. Q2: pick "Generator fails loudly" → reveal → mismatch (writes only First) → **Needs change**. "Matches are accepted with evidence; mismatches are what you actually review."
4. **The drill (45 s)** — Q3 (mixed key kinds, First/Second/Third). The real PR serializes First and Third; the reveal here shows **only First**, because this question is the drill: a bug we planted (M04) and executed. If you predicted "First and Third", the mismatch is the catch → **Needs change** → banner "This was the drill · you caught it". If you accept, the signature gets a **MISSED DRILL** flag. "The tests missed this bug; Gemma caught it; now we measured the human too."
5. **Trust ledger (45 s)** — "How far to trust the AI reviewer": planted bugs table (fields region: tests 0/3, Gemma 3/3), then "Track record of the code this PR changes": `TypeCollector.cs` **trust withdrawn** after the 1a74a620 escape; restored only after 3 calibrated reviews with every planted bug caught and tests ≥ 80 % (this one: union yes, tests 60 %). Stored in Aiven PostgreSQL. Then `B/2283/review.html`: same file, same warning, and a scope-drift story: the agent's test "passes only because of the global filter".
6. **Attestation (60 s)** — "Sign — what you own": what was checked, what was NOT checked, residual risk, name → **Sign review record** → **Download signed record**. Then the verification anyone can do (terminal):
   ```bash
   B=https://yuvrajys2512--earned-trust-receipts-site.us-east.modal.run
   curl -sO $B/2234/attestation/statement.json -sO $B/2234/attestation/statement.json.sig -sO $B/attest/allowed_signers
   ssh-keygen -Y verify -f allowed_signers -I reviewer@earned-trust.example -n earned-trust-review -s statement.json.sig < statement.json
   ```
   Expected: `Good "earned-trust-review" signature for reviewer@earned-trust.example`. Say: "demo key, not a personal identity; in production it's the reviewer's own key."

Close with the card (`B/card.html`): Prove → Predict → Measure → Refuse → Sign, P1–P10, trade-offs, limits.

## C. Things not to say
- Don't say the generator "silently" drops a member without "if MsgPack005 is downgraded" (it's an error by default; Q2 states the downgrade).
- Don't say the injected text "flipped" the reviewer; say it dropped a real finding in 2 of 3 runs (4/6 vs 6/6).
- Don't say "DORA-ready" or "compliant". Don't mention Nemotron results (none exist).
- Minutes are estimates; say "about".
- #2283: the agent added 3 tests, all catching (not "16 placebos": those were pre-existing tests, L-23).
