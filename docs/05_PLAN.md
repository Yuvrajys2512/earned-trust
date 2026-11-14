# 05 — Plan

**Now:** Round 0 — setup + verify the 2234 placebo-test claim. (Update this line after every round.)

Deadline: **Sun 15 Nov 10:00 Helsinki** final submission. Review 14:00. Times below are Helsinki time.

Rule: **every round ends in something demoable**, even if hardcoded. Rounds 1–2 win the challenge; 3–4 get cut first.

## Round 0 — Setup & the decisive check (Sat ~02:00–03:00)
- [ ] Fork the challenge repo; clone; fetch all `ju26-*` branches and tags (`scripts/setup.sh`)
- [ ] Install .NET SDK 8.0.4xx; `dotnet build` the solution on base `32258fdb`
- [ ] Run `scripts/verify_2234_base.sh` → do the agent's new 2234 tests pass on base? Record result in LESSONS_LOG.md
- [ ] Pick the concept name; log in DECISIONS.md
- [ ] Decide stack (Python orchestrator + dotnet CLI); log it
- [ ] Sleep at least a few hours

## Round 1 — Thin slice on #2234, end to end (Sat morning → ~13:00)
- [ ] `git_facts`: file classes + the regression-ancestry check for 2234
- [ ] Hand-write (or LLM-generate) 2–3 catching tests for 2234: duplicate key, mixed key; run on base vs PR
- [ ] Produce `out/2234/record.json` with ≥1 proven behavior change, ≥1 refusal
- [ ] Minimal HTML: question → human types prediction → reveal → sign → record saved
- **Exit:** full flow runs on 2234. You now have a submission.

## Round 2 — Measure the reviewer (Sat ~13:00 → ~18:00)
- [ ] Plant 10 mutants in 2234's changed hunks (Stryker.NET `--since` or LLM mutants)
- [ ] Run the AI reviewer on mutated copies; compute catch rate per file → `calibration`
- [ ] Show "confidence = measured" in the UI
- **Checkpoint 18:00:** if Rounds 1–2 aren't demo-ready, drop Blueprints entirely and cut Round 4.

## Round 3 — Attention budget on #2297 (Sat evening)
- [ ] Classify 237 files; regenerate snapshots from templates; byte-compare → auto-clear 222
- [ ] 2 / 10 / 60-minute slider in the UI
- [ ] Optional: 2283 scope-drift detection (global filter outside requirement)

## Round 4 — Extras (Sat night, only if ahead)
- [ ] Quarantine demo: injected instruction in a PR description → flagged
- [ ] Wire tech-challenge partners for real use (see 07_TECH_CHALLENGES.md)

## Final — Deliverables (Sun ~06:00 → 09:30)
- [ ] Concept card final (03_CONCEPT.md → one slide/page)
- [ ] Record the demo video (live walkthrough of 2234 + 2297 slider)
- [ ] Clean LESSONS_LOG.md, DECISIONS.md, FAILURE_MODES.md
- [ ] Submit by 09:30 (30-min buffer)
