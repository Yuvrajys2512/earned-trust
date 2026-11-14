# 04 — Architecture (reference implementation)

> Proposal — confirm stack choices in Round 0 and log them in DECISIONS.md.

## Pipeline

```
 requirement (issue #) ─┐
 base commit ───────────┼─► [1 Scope] ─► expected-change list (blind to PR text)
 PR commit ─────────────┤
 PR text (untrusted) ───┴─► [0 Quarantine] ─► influence flags
                                │
          ┌─────────────────────┴───────────────────────────┐
          ▼                                                 ▼
 [2 Classify files]                                  [3 Prove behavior]
  generated / template / src / test / docs            generate tests → run on BASE and PR
  regenerate + byte-compare → auto-clear              pass-on-base & fail-on-PR = behavior change
          │                                                 │
          │                                   [4 Tag vs requirement] intended / collateral / unexplained
          │                                                 │
          │                                   [5 Calibrate reviewer] plant mutants in changed hunks
          │                                    → catch rate per file/region = confidence
          └──────────────────────┬──────────────────────────┘
                                 ▼
                       [6 Ask the human] predict-then-reveal questions
                                 ▼
                       [7 Sign] review record JSON (+ HTML view)
```

## Components (suggested)

| Component | Job | Suggested tech |
| --- | --- | --- |
| `orchestrator` | Runs the stages, writes the record | Python 3.11+ (typer CLI) |
| `git_facts` | Diffs, file classes, ancestry checks (e.g. 2234 regression) | `git` subprocess |
| `sandbox` | Build + run tests on base and PR in isolation | Local `dotnet test` first; Modal later (tech challenge) |
| `test_gen` | Generate candidate catching tests from requirement + diff | LLM (reviewer family ≠ author family); C# xUnit output |
| `mutator` | Plant known bugs in changed hunks | Stryker.NET (`dotnet stryker --since`) and/or LLM mutants |
| `reviewer` | AI review pass whose catch rate we measure | LLM (Nemotron / Featherless open model / Codex) |
| `quarantine` | Strip/flag instructions in PR text, hidden HTML comments, zero-width chars | Python regex + small LLM classifier |
| `ui` | Human view: questions, reveal, sign | Single static HTML page reading the record JSON |

## Review record (the signed artifact) — draft schema

```json
{
  "record_version": "0.1",
  "repo": "junction26-messagepack-csharp",
  "requirement": {"id": "#2234", "title": "The analyzer does not work if SuppressSourceGeneration = true", "url": "..."},
  "base": "32258fdb", "head": "9007cee1",
  "author": {"type": "ai", "label": "agent (identity hidden from reviewer)"},
  "reviewer": {"model": "...", "family": "...", "different_family_from_author": true},
  "story_check": {"pr_text_influence_flags": [], "blind_intent": "...", "agent_claims_vs_evidence": []},
  "files": [{"path": "...", "class": "generated|template|src|test|doc", "cleared": true, "evidence": "regenerated, sha256 match"}],
  "behavior_changes": [
    {
      "id": "BC-1",
      "description": "Duplicate [Key(0)] members: second member is dropped silently",
      "evidence": {"test": "DuplicateKey_SecondMemberDropped", "base": "pass", "head": "fail", "log_sha256": "..."},
      "requirement_link": "collateral",
      "question": "Two members share Key(0). What should happen?",
      "human_prediction": "...",
      "revealed_behavior": "...",
      "match": false,
      "decision": "accept|reject|needs-change",
      "rationale": "..."
    }
  ],
  "refusals": [{"topic": "Silent member dropping on duplicate keys", "why": "Not covered by requirement; changes serialization contract"}],
  "calibration": {"planted": 10, "caught": 9, "by_region": {"TypeCollector.cs": "9/10"}, "method": "stryker|llm-mutants"},
  "hearsay": ["LLM statements shown but not proven"],
  "signoff": {"name": "...", "role": "...", "timestamp": "...", "statement": "I predicted before reveal and accept the listed decisions."},
  "record_sha256": "..."
}
```

## Folder conventions
- `src/` — Python package `earned_trust/` (one module per component above).
- `samples/` — synthetic inputs, e.g. `pr_descriptions/injected.md` for the quarantine demo.
- `out/<branch>/` — `record.json`, `report.html`, raw test logs. Gitignored.
- `scripts/` — shell helpers (setup, verification).

## Non-goals
- No GitHub App, no auth, no persistence beyond files. A CLI + one HTML page is enough.
- No model training. No vendor selection (out of scope in the brief).
