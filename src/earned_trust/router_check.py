"""Checks on the risk router itself, so its tiers can be trusted the way we ask the human to trust receipts.

1. Fail-closed self-test: for every PR, remove each input in turn (record, budget, base/head test run, planted-bug
   run, trust ledger, build check) and re-route. A missing input may raise the tier, never lower it.
2. Controls: synthetic changes with a known right answer, committed on the base in a throwaway clone (the challenge
   repo is never written to). Clean controls must not be escalated by the rule they don't trigger; risky controls
   must be caught by the rule written for them. Over-escalations are counted, not hidden: they cost reading, not risk.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import git_facts as gf
from . import tier as tr

INPUTS = ("record", "budget", "ledger", "calibration", "trust", "build")


def load_build(out_dir: Path) -> dict | None:
    """out/<pr>/build/summary.tsv (from scripts/build_<pr>.sh) -> {projects: [...]}, or None if never run."""
    f = out_dir / "build" / "summary.tsv"
    if not f.exists():
        return None
    projects = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        name, code, secs, sha, errs = line.split("\t")
        log = out_dir / "build" / f"{name}.log"
        first, file_ = "", ""
        if log.exists():
            for l in log.read_text(encoding="utf-8", errors="replace").splitlines():
                if " error " in l and ": error " in l:
                    loc, msg = l.split(": error ", 1)
                    file_ = loc.split("-head")[-1].lstrip("\\/").split("(")[0].replace("\\", "/")
                    first = msg.split(" [")[0]
                    break
        projects[name] = {"project": name, "exit": int(code), "seconds": int(secs), "head": sha,
                          "errors": errs.strip() or "none", "first_error": first, "file": file_}
    return {"projects": list(projects.values()), "source": str(f.relative_to(out_dir.parent.parent)).replace("\\", "/")}


def selftest(key: str, repo: str, base: str, head: str, inputs: dict) -> dict:
    full = tr.build(key, repo, base, head, inputs["facts"], **{k: inputs[k] for k in INPUTS})
    cases = []
    for k in INPUTS:
        if inputs[k] is None:
            continue
        res = tr.build(key, repo, base, head, inputs["facts"], **{i: (None if i == k else inputs[i]) for i in INPUTS})
        cases.append({"removed": k, "tier": res["tier"], "full": full["tier"],
                      "ok": tr.RANK[res["tier"]] >= tr.RANK[full["tier"]],
                      "new_rules": [r["id"] for r in res["rules"] if r["fired"]
                                    and r["id"] not in {x["id"] for x in full["rules"] if x["fired"]}]})
    return {"pr": key, "tier": full["tier"], "cases": cases}


# (id, kind, what, edit(path->text), expected tier, rule that must fire, rules that must NOT fire)
def _append(line):
    return lambda t: t.rstrip("\n") + "\n" + line + "\n"


def _first_line(pred, change):
    def f(t):
        ls = t.split("\n")
        i = next(i for i, l in enumerate(ls) if pred(l))
        ls[i] = change(ls[i])
        return "\n".join(ls)
    return f


GU = "src/MessagePack.SourceGenerator/GeneratorUtilities.cs"
CONTROLS = [
    ("C1", "clean", "doc-only sentence in README.md", {"README.md": _append("A sentence added by a control.")},
     "T1", "light-check", ["new-public-api", "circuit-breaker", "no-execution-receipts"]),
    ("C2", "clean", "test-only: a new empty test class",
     {"tests/MessagePack.SourceGenerator.Tests/EtControlTests.cs": lambda t: "namespace EtControl;\n\npublic class EtControlTests\n{\n}\n"},
     "T1", "light-check", ["new-public-api", "no-execution-receipts"]),
    ("C3", "clean", "whitespace-only: trailing spaces on a code line without quotes",
     {GU: _first_line(lambda l: l.rstrip().endswith(";") and '"' not in l and "'" not in l, lambda l: l + "    ")},
     "T0", "whitespace-only", ["no-execution-receipts"]),
    ("C4", "clean", "doc-only line in doc/analyzers/index.md", {"doc/analyzers/index.md": _append("Control line.")},
     "T1", "light-check", ["new-public-api"]),
    ("C5", "clean", "comment-only line in generator code (not a withdrawn region)", {GU: _append("// control comment")},
     "T1", None, []),
    ("R1", "risky", "adds a public attribute class to MessagePack.Annotations",
     {"src/MessagePack.Annotations/Attributes.cs": _append("public class EtControlAttribute : System.Attribute { }")},
     "T3", "new-public-api", []),
    ("R2", "risky", "adds diagnostic MsgPack099 to AnalyzerReleases.Unshipped.md",
     {"src/MessagePack.SourceGenerator/AnalyzerReleases.Unshipped.md": _append("MsgPack099 | Usage | Error | Control")},
     "T3", "new-public-api", []),
    ("R3", "risky", "edits TypeCollector.cs (trust withdrawn after an escape)",
     {"src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs": _append("// control edit")},
     "T3", "circuit-breaker", []),
    ("R4", "risky", "behavior edit in generator code with no base/head test run",
     {GU: _first_line(lambda l: ".Collect();" in l, lambda l: l.replace(".Collect();", ".Collect().Select(static (a, ct) => a);", 1))},
     "T3", "no-execution-receipts", []),
    ("R5", "risky", "whitespace inside a string literal (looks whitespace-only to git diff -w)",
     {GU: _first_line(lambda l: '$"{AttributeNamespace}.' in l, lambda l: l.replace('$"{AttributeNamespace}.', '$"{AttributeNamespace} .', 1))},
     "T3", "no-execution-receipts", ["whitespace-only"]),
]


def _sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True).stdout


def controls(src_repo: str, base: str, work: Path, trust: dict | None) -> dict:
    clone = work / "repo"
    if not (clone / ".git").exists():
        work.mkdir(parents=True, exist_ok=True)
        _sh(str(work), "git", "clone", "--quiet", "--shared", "--no-checkout", src_repo, "repo")
    rows = []
    for cid, kind, what, edits, expect, must, must_not in CONTROLS:
        _sh(str(clone), "git", "checkout", "--quiet", "--force", "--detach", base)
        _sh(str(clone), "git", "clean", "-fdq")
        for path, fn in edits.items():
            p = clone / path
            old = p.read_text(encoding="utf-8") if p.exists() else ""
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(fn(old), encoding="utf-8", newline="")
        _sh(str(clone), "git", "add", "-A")
        _sh(str(clone), "git", "-c", "user.name=et-control", "-c", "user.email=control@earned-trust.example",
            "-c", "core.autocrlf=false", "commit", "--quiet", "-m", f"control {cid}: {what}")
        head = _sh(str(clone), "git", "rev-parse", "HEAD").strip()
        facts = {"files": [gf.to_dict(f) for f in gf.changed_files(str(clone), base, head)]}
        res = tr.build(cid, str(clone), base, head, facts, trust=trust)
        fired = [r["id"] for r in res["rules"] if r["fired"]]
        ok_rule = must is None or must in fired
        ok_not = not any(r in fired for r in must_not)
        rows.append({"id": cid, "kind": kind, "change": what, "expected": expect, "tier": res["tier"], "fired": fired,
                     "must_fire": must, "must_not_fire": must_not, "files": [f["path"] for f in facts["files"]],
                     "pass": res["tier"] == expect and ok_rule and ok_not,
                     "over_escalated": tr.RANK[res["tier"]] > tr.RANK[expect],
                     "under_escalated": tr.RANK[res["tier"]] < tr.RANK[expect]})
    _sh(str(clone), "git", "checkout", "--quiet", "--force", "--detach", base)
    return {"base": base, "rows": rows,
            "clean": {"n": sum(r["kind"] == "clean" for r in rows),
                      "false_alarms": sum(r["kind"] == "clean" and r["over_escalated"] for r in rows)},
            "risky": {"n": sum(r["kind"] == "risky" for r in rows),
                      "caught": sum(r["kind"] == "risky" and r["pass"] for r in rows),
                      "missed": sum(r["kind"] == "risky" and r["under_escalated"] for r in rows)}}
