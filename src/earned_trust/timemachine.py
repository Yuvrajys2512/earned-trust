"""Time Machine: replay the review factory on the commit that caused a reported bug.

Trust is earned on history. Before a reviewer may clear changes in a repo, show what it would
have done on that repo's own past regressions. For #2234 the origin is 1a74a620 (upstream PR #2106).

Inputs: TRX runs from scripts/timemachine_<pr>.sh (base = parent of the bad commit, head = bad commit)
plus GitHub facts fetched read-only with `gh api` (cached to disk so the demo works offline).
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from . import prove as pv

# What we ask GitHub, and why. Every fact keeps the command that produced it.
GH_QUERIES = {
    "pr": ("repos/MessagePack-CSharp/MessagePack-CSharp/pulls/{pr}",
           "{title, author: .user.login, merged_by: .merged_by.login, merged_at, created_at, "
           "changed_files, additions, deletions, commits, html_url}"),
    "reviews": ("repos/MessagePack-CSharp/MessagePack-CSharp/pulls/{pr}/reviews",
                "[.[] | {user: .user.login, state, submitted_at}]"),
    "issue": ("repos/MessagePack-CSharp/MessagePack-CSharp/issues/{issue}",
              "{title, created_at, state, comments, html_url}"),
}


def github_facts(pr: int, issue: int, cache: Path) -> dict:
    facts = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    for key, (path, jq) in GH_QUERIES.items():
        url = path.format(pr=pr, issue=issue)
        cmd = ["gh", "api", url, "--jq", jq]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if r.returncode == 0:
            facts[key] = {"value": json.loads(r.stdout), "command": f"gh api {url} --jq '{jq}'"}
        elif key not in facts:
            facts[key] = {"value": None, "command": f"gh api {url}", "error": r.stderr.strip()[:200]}
    cache.write_text(json.dumps(facts, indent=2), encoding="utf-8")
    return facts


def diag_summary(message: str) -> str:
    """Turn a Roslyn analyzer-test failure into the one fact a human needs."""
    if not message:
        return ""
    m = re.search(r'expected "(\d+)" actual "(\d+)"', message)
    if m:
        return f"expected {m.group(1)} diagnostic(s), analyzer reported {m.group(2)}"
    m = re.search(r"Expected diagnostic to start on line \"(\d+)\" was actually on line \"(\d+)\"", message)
    if m:
        return f"diagnostic reported, but on line {m.group(2)} instead of {m.group(1)} (test written for newer code)"
    if "AD0001" in message or "same key has already been added" in message:
        return "analyzer crashed (AD0001)"
    return message.strip().splitlines()[0][:160]


def build(run_dir: Path, pr: int, issue: int, bad: str, parent: str) -> dict:
    ledger = pv.build_ledger(run_dir)
    gh = github_facts(pr, issue, run_dir / "github.json")
    entries = []
    for e in ledger["entries"]:
        entries.append({
            "test": e["test"], "verdict": e["verdict"],
            "parent": e["base"]["outcome"], "bad_commit": e["head"]["outcome"],
            "parent_says": diag_summary(e["base"]["message"]),
            "bad_commit_says": diag_summary(e["head"]["message"]),
            "trx_sha256": e["head"]["trx_sha256"],
        })
    caught = [x for x in entries if x["verdict"] == "broken-by-pr"]
    silenced = [x for x in entries if "reported 0" in x["bad_commit_says"] and "reported 0" not in x["parent_says"]]
    reviews = (gh.get("reviews") or {}).get("value")
    p = (gh.get("pr") or {}).get("value") or {}
    i = (gh.get("issue") or {}).get("value") or {}
    return {
        "question": f"Would this factory have caught the origin of {issue and '#' + str(issue)} when it was introduced?",
        "bad_commit": bad, "parent": parent,
        "method": "agent's #2234 tests (unchanged) run on the parent and on the commit that introduced the bug; "
                  "pass-on-parent + fail-on-commit = the gate would have gone red",
        "verdict": "would-have-caught" if caught else "would-not-have-caught",
        "caught_by": [x["test"] for x in caught],
        "silenced_diagnostics": [x["test"] for x in silenced],
        "history": {
            "pr": p, "reviews": reviews, "review_count": None if reviews is None else len(reviews),
            "self_merged": bool(p) and p.get("author") == p.get("merged_by"),
            "issue": i,
            "commands": {k: v["command"] for k, v in gh.items()},
        },
        "counts": ledger["counts"],
        "entries": entries,
    }
