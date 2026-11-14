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


def build_record(pr, facts: dict, ledger: dict, spec: dict, evidence_dir: Path) -> dict:
    tests = _by_test(ledger)
    hearsay: list[str] = []

    changes = []
    for bc in spec["behavior_changes"]:
        evidence, missing = [], []
        for t in bc["tests"]:
            (evidence.append(_ev(tests[t])) if t in tests else missing.append(t))
        proven = bool(evidence) and not missing and all(e["verdict"] == "catching" for e in evidence)
        if not proven:
            hearsay.append(f"{bc['id']}: '{bc['title']}' — cited tests are not all catching "
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
    reviewer_tests = [e for e in ledger["entries"] if e["test"].startswith("EtGeneratorReceiptsTests.")]
    agent_tests = [e for e in ledger["entries"] if not e["test"].startswith("EtGeneratorReceiptsTests.")]

    def counts(entries):
        out: dict[str, int] = {}
        for e in entries:
            out[e["verdict"]] = out.get(e["verdict"], 0) + 1
        return out

    checked = [
        f"Git history: is the regression named in {pr.requirement.id} in this code's history? "
        f"→ {facts.get('regression_check', {}).get('verdict', 'n/a')}",
        f"Agent's {len(agent_tests)} new tests run on base and on head: {counts(agent_tests)}",
        f"Reviewer's {len(reviewer_tests)} own catching tests (source generator output) run on base and head: "
        f"{counts(reviewer_tests)}",
        f"{len(facts['files'])} changed files classified: {facts['file_classes']}",
    ]

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
        "calibration": {"status": "not-measured",
                        "note": "Planted-bug catch rate not yet run (Round 2). Treat the AI reviewer as uncalibrated."},
        "hearsay": hearsay,
        "signoff": None,
    }
    body = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    record["evidence_sha256"] = hashlib.sha256(body).hexdigest()
    return record
