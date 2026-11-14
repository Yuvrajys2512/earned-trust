# 07 — Tech challenges (partner prizes)

Rule: integrate a partner only where it is **load-bearing** in the concept (judges reward "best use", not logos). Tiers set by the owner on Sat 14 Nov.

## Tier A — we build these anyway

| Partner | Prize | Role in *Receipts, not reviews* | What their judges need | Status |
| --- | --- | --- | --- | --- |
| **OpenAI Codex** | $10k/$5k/$2.5k credits | Build agent for this repo **and** the *author agent* whose PRs we review (author ≠ reviewer family, P-reviewer≠author) | Meaningful use while building; claim $100/participant | TODO |
| **NVIDIA Nemotron** | 2× RTX 5080 | **The reviewer model.** Must be *Nemotron 3.5 Super VL*. Submission text: what the model does + how we improved outputs → planted-bug catch rate before/after prompt changes (25% of score = quality improved through evaluation) | Short text in submission form | TODO |
| **Modal** | $2k cash + $3k credits | Sandboxes run untrusted agent code: base/head catching tests + mutants in parallel. `modal deploy` the review UI → live URL (demo = 15%) | Live deployed URL. Credit code `VVX-2QX-8HW` | TODO |

## Tier B — ~1 h each, genuinely part of the system

| Partner | Prize | Role | Status |
| --- | --- | --- | --- |
| **Entire** (MLH) | projector | Record author-agent sessions (Sessions); publish the review record as a **Trail** (agent reviews whether change matches intent); use Graph + Brain where possible. mlh.link/junction-26 | TODO |
| **Gemma** | €1,000 ×3 | Second, independent reviewer from a different family (counters self-preference, F-09); run on Modal | TODO |
| **Aiven** | €1k/€750/€500 | Postgres: signed review records + reviewer track record across PRs → trust is *earned per area* and withdrawn after escapes | TODO |

## Tier C — only if ahead

| Partner | Role |
| --- | --- |
| CRACI | CI `runs-on: craci`; pull the PR build's SBOM into the record as supply-chain evidence (security part of the brief). Invite code in #craci |
| Verda | Hosted Nemotron endpoint → "agent code never leaves EU infrastructure". Must document process + post summary in their Discord |
| Gemini API | Could generate catching tests; most crowded — skip |
