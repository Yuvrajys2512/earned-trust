"""Record stage: join executed evidence (facts + ledger) with the reviewer spec.

The spec is *claims*; the ledger and facts are *receipts*. This module refuses to
let a claim through on the spec's word: a behavior change is `proven` only if every
test it cites is `catching` in the ledger. Otherwise it is downgraded to `hearsay`.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _by_test(ledger: dict) -> dict[str, dict]:
    return {e["test"]: e for e in ledger["entries"]}


def _ev(entry: dict) -> dict:
    return {
        "ledger_id": entry["id"],
        "test": entry["test"],
        "verdict": entry["verdict"],
        "base": entry["base"]["outcome"],
        "head": entry["head"]["outcome"],
        "signal": entry["signal"],
        "trx_sha256": entry["head"]["trx_sha256"] or entry["base"]["trx_sha256"],
    }


CAUGHT = (True, "killed", "killed-by-compiler")


def calibration_block(cal: dict | None) -> dict:
    """Planted-bug results -> what the human sees as 'how far to trust each screener on THIS PR'."""
    if not cal or "summary" not in cal:
        return {"status": "not-measured",
                "note": "No planted-bug run for this PR. Treat the AI reviewer as uncalibrated."}
    sm = cal["summary"]
    screeners = ["tests"] + [k for k in sm if k.startswith("reviewer:") and isinstance(sm[k], dict) and "caught" in sm[k]]
    rows = sm["rows"]
    union = sum(1 for r in rows if any(r.get(s) in CAUGHT for s in screeners))
    missed_by_all = [r["id"] for r in rows if not any(r.get(s) in CAUGHT for s in screeners)]
    controls = {k.split(":")[1]: sm[k] for k in sm if k.endswith(":control_findings")}
    return {
        "status": "measured",
        "method": "Known bugs planted one at a time in the PR's changed regions (hidden from the reviewer, "
                  "like Threat Image Projection in airport screening). Tests: does any test go red? "
                  "Reviewer: does a finding cite the planted spot? Unknown (no answer) is never counted as caught or missed.",
        "planted": sm["planted"],
        "screeners": {s: sm[s] for s in screeners if s in sm},
        "models": {k.split(":")[1]: sm[k] for k in sm if k.endswith(":model")},
        "union_caught": union,
        "missed_by_all": missed_by_all,
        "by_region": sm["by_region"],
        "rows": rows,
        "reviewer_on_real_pr": {name: (len(f) if f is not None else None) for name, f in controls.items()},
        "reviewer_on_real_pr_findings": controls,
    }


def build_record(pr, facts: dict, ledger: dict, spec: dict, evidence_dir: Path, calibration: dict | None = None,
                 budget: dict | None = None) -> dict:
    tests = _by_test(ledger)
    hearsay: list[str] = []

    changes = []
    for bc in spec["behavior_changes"]:
        evidence, missing = [], []
        for t in bc["tests"]:
            (evidence.append(_ev(tests[t])) if t in tests else missing.append(t))
        # The spec may say which ledger verdict proves this change (a regression is proven by
        # `broken-by-pr`, a gap by `failing-both`); the ledger, not the spec, decides if it holds.
        expect = bc.get("expect", "catching")
        proven = bool(evidence) and not missing and all(e["verdict"] == expect for e in evidence)
        if not proven:
            hearsay.append(f"{bc['id']}: '{bc['title']}' — cited tests are not all {expect} "
                           f"(missing: {missing or 'none'}); shown as unproven.")
        files = {}
        for name in bc.get("evidence_files", []):
            for side in ("base", "head"):
                f = evidence_dir / side / name
                if f.exists():
                    files.setdefault(name, {})[side] = f.read_text(encoding="utf-8")
        changes.append({
            "id": bc["id"],
            "title": bc["title"],
            "status": "proven" if proven else "unproven",
            "proven_by": expect,
            "requirement_link": bc["requirement_link"],
            "link_why": bc["link_why"],
            "evidence": evidence,
            "generated_output": files,
            "question": bc["question"],
        })

    claims = []
    for c in spec.get("story_claims", []):
        ev = [_ev(tests[t]) for t in c.get("tests", []) if t in tests]
        verdict = c["verdict"]
        if c.get("tests") and verdict == "true-but-not-new":
            # recompute: only allowed if the cited tests really pass on base
            if not ev or not all(e["verdict"] == "placebo" for e in ev):
                verdict = "unverified"
        claims.append({**c, "verdict": verdict, "evidence": ev})

    placebos = [_ev(e) for e in ledger["entries"] if e["verdict"] == "placebo"]
    # Reviewer-written receipts are named Et*Tests (receipts/<pr>/); everything else is the agent's.
    reviewer_tests = [e for e in ledger["entries"] if e["test"].startswith("Et")]
    agent_tests = [e for e in ledger["entries"] if not e["test"].startswith("Et")]

    def counts(entries):
        out: dict[str, int] = {}
        for e in entries:
            out[e["verdict"]] = out.get(e["verdict"], 0) + 1
        return out

    def fmt(d: dict) -> str:
        return ", ".join(f"{v} {k}" for k, v in sorted(d.items(), key=lambda kv: -kv[1]))

    checked = []
    if facts.get("regression_check"):
        checked.append(f"Git history: is the regression named in {pr.requirement.id} in this code's history? "
                       f"→ {facts['regression_check']['verdict']}")
    checked += [
        f"Agent's {len(agent_tests)} new tests run on base and on head: {fmt(counts(agent_tests))}",
        f"Reviewer's {len(reviewer_tests)} own tests of the source generator's output, run on base and head: "
        f"{fmt(counts(reviewer_tests))}",
        f"{len(facts['files'])} changed files classified: {fmt(facts['file_classes'])}",
    ]
    ab = None
    if budget:
        t = budget["totals"]
        ab = {"totals": t, "assumptions": budget["assumptions"], "regen": budget.get("regen"),
              "human_files": [{k: i[k] for k in ("path", "cls", "why", "minutes", "cumulative_minutes")} for i in budget["human"]],
              "machine_receipts_sha256": hashlib.sha256(json.dumps(budget["machine"], sort_keys=True).encode()).hexdigest()}
        checked.append(f"{t['machine_cleared']} of {t['files']} files cleared by executed checks (snapshot regenerate + "
                       f"byte compare, T4 output consistency); {t['human']} left for the human "
                       f"(~{t['human_minutes']} min est., vs ~{t['naive_minutes']} to read everything)")
    cb = calibration_block(calibration)
    if cb["status"] == "measured":
        checked.append(f"{cb['planted']} known bugs planted in the changed code: " + "; ".join(
            f"{'tests' if k == 'tests' else k.split(':')[1]} caught {v['caught']}/{v['measured']}"
            for k, v in cb["screeners"].items()) + f"; at least one screener caught {cb['union_caught']}/{cb['planted']}")

    record = {
        "record_version": "0.2",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repo": "te-industry-tech-office/junction26-messagepack-csharp",
        "requirement": {**facts["requirement"], "summary": pr.requirement.summary},
        "base": facts["base"],
        "head": facts["head"],
        "author": {"type": "ai-agent", "label": "author agent (identity hidden from the reviewer)"},
        "reviewer": {"spec_author": spec["spec_author"], "model": None,
                     "note": "v0: no model in the loop yet; all verdicts come from executed tests"},
        "toolchain": ledger.get("toolchain", {"sdk": "9.0.x (global.json overridden, L-04)"}),
        "blind_intent": spec["blind_intent"],
        "files": facts["files"],
        "file_classes": facts["file_classes"],
        "regression_check": facts.get("regression_check"),
        "ledger_counts": {"agent_tests": counts(agent_tests), "reviewer_tests": counts(reviewer_tests)},
        "placebo_tests": placebos,
        "behavior_changes": changes,
        "refusals": spec["refusals"],
        "story_claims": claims,
        "checked": checked,
        "not_checked": spec["not_checked"],
        "calibration": calibration_block(calibration),
        "attention_budget": ab,
        "hearsay": hearsay,
        "signoff": None,
    }
    body = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    record["evidence_sha256"] = hashlib.sha256(body).hexdigest()
    return record
