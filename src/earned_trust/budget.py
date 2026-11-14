"""Attention budget: spend human minutes only where a machine can't give a receipt.

Every changed file gets a lane:

  machine   cleared by an executed check, with the check and its result attached
            (snapshot regenerated + byte-identical; T4 output consistent with its template)
  human     needs eyes: hand-written source, templates, tests, docs, and anything a
            machine check failed on (a failed check is never silently cleared)

The human lane is then ordered by priority so a 2 / 10 / 60-minute budget shows what
gets read first and what is knowingly left unread. Minutes are an estimate
(changed lines / READ_RATE, at least MIN_MINUTES per file) and are labelled as such.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

READ_RATE = 20      # changed lines a reviewer reads carefully per minute (assumption, shown in UI)
MIN_MINUTES = 0.5   # opening a file and finding the hunk costs something

PRIORITY = {"src": 0, "template": 1, "test": 2, "template-output": 3, "generated": 3, "doc": 4, "build": 4}


def git_show(repo: str, rev: str, path: str) -> str:
    r = subprocess.run(["git", "-C", repo, "show", f"{rev}:{path}"], capture_output=True, text=True, encoding="utf-8")
    return r.stdout if r.returncode == 0 else ""


# --- T4: is the committed .cs what its .tt would produce? ----------------------

_LIT = re.compile(r'@"((?:[^"]|"")*)"|"((?:[^"\\\n]|\\.)*)"', re.S)
_ESC = {"r": "\r", "n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'", "0": "\0"}


def written_text(cs: str) -> str:
    """Concatenate every string literal passed to this.Write(...) in a T4-preprocessed .cs file."""
    out = []
    for m in re.finditer(r"this\.Write\(", cs):
        i = m.end()
        while True:
            while i < len(cs) and cs[i] in " \t\r\n+":
                i += 1
            lm = _LIT.match(cs, i)
            if not lm:
                break
            if lm.group(1) is not None:
                out.append(lm.group(1).replace('""', '"'))
            else:
                out.append(re.sub(r"\\(.)", lambda e: _ESC.get(e.group(1), e.group(0)), lm.group(2)))
            i = lm.end()
        out.append("\n")
    return "".join(out).replace("\r\n", "\n")


def tt_text(tt: str) -> str:
    """Template text with control blocks (<# ... #>) removed; expression blocks become a marker."""
    tt = tt.replace("\r\n", "\n")
    tt = re.sub(r"<#=.*?#>", "\x00", tt, flags=re.S)
    return re.sub(r"<#.*?#>", "", tt, flags=re.S)


def t4_consistency(repo: str, base: str, head: str, tt_path: str) -> dict:
    """For every text line the PR added to the .tt, it must occur in the .cs output the same number
    of times it occurs in the template text, at head; and the .cs must have changed by the same lines.
    A string-level check of the committed output, not a re-run of Visual Studio's T4 engine."""
    cs_path = tt_path[:-3] + ".cs"
    tt_b, tt_h = git_show(repo, base, tt_path), git_show(repo, head, tt_path)
    out_b, out_h = written_text(git_show(repo, base, cs_path)), written_text(git_show(repo, head, cs_path))
    txt_b, txt_h = tt_text(tt_b), tt_text(tt_h)
    added = sorted({ln.strip() for ln in tt_h.replace("\r\n", "\n").split("\n")} -
                   {ln.strip() for ln in tt_b.replace("\r\n", "\n").split("\n")} - {""})
    checks = []
    for ln in added:
        if "<#" in ln or "#>" in ln:
            checks.append({"line": ln, "ok": None, "why": "contains T4 code; not checkable at string level"})
            continue
        want = sum(1 for x in txt_h.split("\n") if x.strip() == ln)
        got = sum(1 for x in out_h.split("\n") if x.strip() == ln)
        was = sum(1 for x in out_b.split("\n") if x.strip() == ln)
        want_was = sum(1 for x in txt_b.split("\n") if x.strip() == ln)
        ok = want == got and (got - was) == (want - want_was)
        checks.append({"line": ln, "ok": ok, "template_count": want, "output_count": got, "output_count_at_base": was})
    verdict = "consistent" if checks and all(c["ok"] is not False for c in checks) else "inconsistent"
    return {"template": tt_path, "output": cs_path, "verdict": verdict, "checks": checks,
            "method": "string-level: decoded this.Write literals vs template text lines added by the PR"}


# --- the budget ------------------------------------------------------------------

def minutes(f: dict) -> float:
    return max(MIN_MINUTES, round((f["added"] + f["deleted"]) / READ_RATE, 1))


def build(repo: str, base: str, head: str, facts: dict, regen: dict | None) -> dict:
    regen_by_path = {r["path"]: r for r in (regen or {}).get("files", [])}
    t4 = {}
    for f in facts["files"]:
        if f["cls"] == "template":
            r = t4_consistency(repo, base, head, f["path"])
            t4[r["output"]] = r

    items = []
    for f in facts["files"]:
        it = {"path": f["path"], "cls": f["cls"], "added": f["added"], "deleted": f["deleted"], "minutes": minutes(f)}
        if f["cls"] == "generated":
            r = regen_by_path.get(f["path"])
            if r and r["verdict"] == "identical":
                it.update(lane="machine", receipt=f"regenerated from head templates: blob {r['regen_blob'][:10]} == PR blob")
            else:
                it.update(lane="human", why=f"snapshot not reproduced ({r['verdict'] if r else 'no regen run'})")
        elif f["cls"] == "template-output":
            r = t4.get(f["path"])
            if r and r["verdict"] == "consistent":
                it.update(lane="machine", receipt=f"{len(r['checks'])} added template line(s) appear in output with matching counts")
            else:
                it.update(lane="human", why="T4 output not shown consistent with its template")
        else:
            it.update(lane="human", why={"src": "hand-written source", "template": "the actual change (generates all snapshots)",
                                         "test": "agent-written test: what does it really assert?", "doc": "user-facing claim"}.get(f["cls"], f["cls"]))
        it["priority"] = PRIORITY.get(f["cls"], 5)
        items.append(it)

    human = sorted((i for i in items if i["lane"] == "human"), key=lambda i: (i["priority"], -i["added"] - i["deleted"]))
    t = 0.0
    for i in human:
        t += i["minutes"]
        i["cumulative_minutes"] = round(t, 1)
    machine = [i for i in items if i["lane"] == "machine"]
    return {
        "head": head, "base": base,
        "assumptions": {"read_rate_lines_per_min": READ_RATE, "min_minutes_per_file": MIN_MINUTES},
        "totals": {
            "files": len(items),
            "machine_cleared": len(machine),
            "human": len(human),
            "naive_minutes": round(sum(i["minutes"] for i in items), 1),
            "human_minutes": round(sum(i["minutes"] for i in human), 1),
        },
        "regen": {k: v for k, v in (regen or {}).items() if k != "files"},
        "t4": list(t4.values()),
        "human": human,
        "machine": machine,
    }
