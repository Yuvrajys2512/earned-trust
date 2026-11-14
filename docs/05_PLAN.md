# 05 — Plan

**Now:** UI pass done and live (Sat ~20:05 Helsinki): shared FX layer (receipt machine, reveal stamps, time-machine rewind, planted-bug grid, 237→9 triage, printed receipt), phone-width fixed, attestations still VALID (L-25, F-45). Submission text drafted (`docs/11_SUBMISSION.md`, needs repo + video links). Next: sleep 23:30–05:00; Sunday record the video from `docs/10_WALKTHROUGH.md`, submit by 09:30. (Update this line after every round.)

Deadline: **Sun 15 Nov 10:00 Helsinki** final submission. Review 14:00. Times below are Helsinki time.

Rule: **every round ends in something demoable**, even if hardcoded. Rounds 1–2 win the challenge; 3–4 get cut first.

## Round 0 — Setup & the decisive check (Sat ~02:00–03:00)
- [x] Clone (no fork needed, see DECISIONS); fetch all `ju26-*` branches and tags (`scripts/setup.sh`)
- [x] Install .NET SDK 8.0.428 + 9.0.321 (9 needed for ExecutionTests, L-04); build on base `32258fdb`
- [x] Run `scripts/verify_2234_base.sh` → do the agent's new 2234 tests pass on base? Record result in LESSONS_LOG.md
- [x] Pick the concept name; log in DECISIONS.md → **Receipts, not reviews**
- [x] Decide stack (Python orchestrator + dotnet CLI); log it
- [ ] Sleep at least a few hours

## Round 1 — Thin slice on #2234, end to end (Sat morning → ~13:00)
- [x] `git_facts`: file classes + the regression-ancestry check for 2234 (`uv run et facts all`)
- [x] Turn verify script into `et prove`: per-test base/head outcome → ledger (placebo / catching), parsed from TRX
- [x] Write our *own* catching tests for 2234 beyond the agent's: generator output when MsgPack005 is suppressed (first-wins vs crash)
- [x] Produce `out/2234/record.json` with ≥1 proven behavior change, ≥1 refusal
- [x] Minimal HTML: question → human types prediction → reveal → sign → record saved
- **Exit:** full flow runs on 2234. You now have a submission.

## Round 2 — Measure the reviewer (Sat ~13:00 → ~18:00)
- [x] Plant 10 mutants in 2234's changed hunks (hand-written operators, `src/earned_trust/mutate.py`)
- [x] Run the AI reviewer on mutated copies; compute catch rate per region → `calibration` (Gemma now; Nemotron pending access)
- [x] Show "confidence = measured" in the UI
- **Checkpoint 18:00:** if Rounds 1–2 aren't demo-ready, drop Blueprints entirely and cut Round 4.

## Round 3 — Attention budget on #2297 (Sat evening)
- [x] Classify 237 files; regenerate snapshots from templates; byte-compare → auto-clear 222 (`scripts/regen_2297.sh`, `et budget`)
- [x] 2 / 10 / 60-minute selector in the UI (`out/2297/budget.html`)
- [x] Base-vs-head ledger for 2297 with reviewer receipts (`scripts/verify_2297_base.sh`, `et prove 2297`)
- [x] 2297 review spec (`receipts/2297/review.json`) → record + predict-then-reveal page (3 proven: change, regression, gap; 2 refusals)
- [ ] Optional: 2283 scope-drift detection (global filter outside requirement)

## Round 4 — Extras (Sat night, only if ahead)
- [ ] Quarantine demo: injected instruction in a PR description → flagged
- [ ] Wire tech-challenge partners for real use (see 07_TECH_CHALLENGES.md)

## Final — Deliverables (Sun ~06:00 → 09:30)
- [x] Concept card final (03_CONCEPT.md → one slide/page: `card.html`)
- [ ] Record the demo video (live walkthrough of 2234 + 2297 slider)
- [x] Clean LESSONS_LOG.md, DECISIONS.md, FAILURE_MODES.md
- [ ] Submit by 09:30 (30-min buffer)
