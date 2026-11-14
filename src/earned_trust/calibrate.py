"""Calibrate stage, part 2: measure the screeners on planted bugs.

  tests    - each mutant is written into the HEAD worktree, the PR's tests + reviewer
             receipts run; killed = any test fails (or the build breaks).
  reviewer - the reviewer model sees requirement + diff(base -> head-with-mutant),
             never the PR story, never told a bug was planted. caught = a finding
             cites a line within ±LINE_SLACK of a planted line. A control run on the
             real PR (no mutant) measures what it reports when nothing is planted.

The reviewer's catch rate on *this PR's* code is its confidence for this PR (P2).
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import subprocess
import time
from pathlib import Path

from . import models
from . import mutate as mu
from .prove import parse_trx

ROOT = Path(__file__).resolve().parents[2]
LINE_SLACK = 3
CR, LF = chr(13), chr(10)
CRLF = CR + LF

TEST_FILTER = ("FullyQualifiedName~SuppressSourceGenerationAnalyzerTests|"
               "FullyQualifiedName~EtGeneratorReceiptsTests")
TEST_PROJECT = "tests/MessagePack.SourceGenerator.Tests/MessagePack.SourceGenerator.Tests.csproj"


def git_show(repo: str, ref: str, path: str) -> str:
    return subprocess.run(["git", "-C", repo, "show", f"{ref}:{path}"], capture_output=True,
                          text=True, encoding="utf-8", check=True).stdout


# ---------------------------------------------------------------- tests as screener

def dotnet_env() -> dict:
    """Same as scripts/env.sh, without depending on which `bash` is on PATH (WSL vs Git Bash)."""
    env = dict(os.environ)
    root = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "dotnet" if os.name == "nt" else Path.home() / ".dotnet"
    if (root / ("dotnet.exe" if os.name == "nt" else "dotnet")).exists():
        env["DOTNET_ROOT"] = str(root)
        env["PATH"] = str(root) + os.pathsep + env.get("PATH", "")
        # Windows CreateProcess resolves the exe with the *parent's* PATH, so pass the full path (L-09).
        env["ET_DOTNET"] = str(root / ("dotnet.exe" if os.name == "nt" else "dotnet"))
    env.update(DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1", DOTNET_MULTILEVEL_LOOKUP="0")
    return env


def run_tests_on_mutants(worktree: Path, out_dir: Path, mutants: list[mu.Mutant]) -> dict:
    target = worktree / mu.TARGET
    original = target.read_bytes()
    out_dir.mkdir(parents=True, exist_ok=True)
    text = original.decode("utf-8")
    crlf = CRLF in text                               # Windows checkouts: mutate in LF, write back in CRLF
    text = text.replace(CRLF, LF)
    env = dotnet_env()
    results = {}
    try:
        for m in [None, *mutants]:                       # None = control (unmutated head)
            mid = m.id if m else "control"
            if m:
                src, _ = mu.apply(text, m)
                target.write_bytes((src.replace(LF, CRLF) if crlf else src).encode("utf-8"))
            else:
                target.write_bytes(original)
            trx = out_dir / f"{mid}.trx"
            trx.unlink(missing_ok=True)
            cmd = [env.get("ET_DOTNET", "dotnet"), "test", TEST_PROJECT, "--filter", TEST_FILTER, "--logger", f"trx;LogFileName={trx}"]
            t0 = time.time()
            proc = subprocess.run(cmd, cwd=worktree, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
            (out_dir / f"{mid}.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
            if trx.exists():
                outcomes = parse_trx(trx)
                failed = sorted(t for t, o in outcomes.items() if o.outcome != "Passed")
                status = "killed" if failed else "survived"
                res = {"status": status, "failed_tests": failed, "tests_run": len(outcomes)}
            else:
                build_err = "error CS" in proc.stdout
                res = {"status": "killed-by-compiler" if build_err else "unknown", "failed_tests": [], "tests_run": 0}
            res["seconds"] = round(time.time() - t0)
            results[mid] = res
            print(f"   tests  {mid:<8} {res['status']:<18} {len(res['failed_tests'])} failing  ({res['seconds']}s)", flush=True)
    finally:
        target.write_bytes(original)                     # never leave a mutant behind
    return results


# ---------------------------------------------------------------- reviewer as screener

REVIEW_SYSTEM = """You are a senior C# reviewer for the MessagePack-CSharp source generator and analyzer.
You review a code change against its requirement. Report concrete defects only: logic errors,
behavior changes that can lose or corrupt data, crashes, missing diagnostics, inconsistencies
between duplicated code paths. Do not report style. Each finding must cite the exact line number
shown in the left column of the diff (new-file numbering). If you find nothing, return an empty list.
Respond with JSON only:
{"findings":[{"file":"...","line":123,"severity":"high|medium|low","title":"...","explanation":"..."}]}"""


def review_prompt(requirement: str, diff: str) -> str:
    return (f"REQUIREMENT\n{requirement}\n\n"
            f"CHANGE (unified diff; left column = new-file line number; '+' added, '-' removed)\n{diff}\n")


def review_once(model: models.Model, requirement: str, diff: str) -> dict:
    reply = model.complete(REVIEW_SYSTEM, review_prompt(requirement, diff))
    out = {"model": reply.model, "family": reply.family, "attempts": reply.attempts, "error": reply.error}
    if reply.error:
        out["findings"] = None
        return out
    try:
        data = models.extract_json(reply.text)
        out["findings"] = data.get("findings", []) if isinstance(data, dict) else data
    except ValueError as e:
        out["findings"], out["error"] = None, f"unparseable reply: {e}"
        out["raw"] = reply.text[:2000]
    return out


def caught(findings: list[dict] | None, planted: list[int]) -> tuple[bool | None, list[dict]]:
    if findings is None:
        return None, []                                   # reviewer didn't answer -> unknown, not "missed"
    hits = []
    for f in findings:
        try:
            line = int(f.get("line"))
        except (TypeError, ValueError):
            continue
        if "TypeCollector" in str(f.get("file", "TypeCollector")) and any(abs(line - p) <= LINE_SLACK for p in planted):
            hits.append(f)
    return bool(hits), hits


def run_reviewer_on_mutants(repo: str, base: str, head_ref: str, requirement: str,
                            model: models.Model, mutants: list[mu.Mutant], workers: int = 4,
                            control: bool = True) -> dict:
    base_src = git_show(repo, base, mu.TARGET)
    head_src = git_show(repo, head_ref, mu.TARGET)

    def job(m: mu.Mutant | None):
        if m is None:
            diff = mu.numbered_diff(mu.TARGET, base_src, head_src)
            r = review_once(model, requirement, diff)
            r["planted_lines"] = []
            return "control", r
        msrc, _ = mu.apply(head_src, m)
        planted = mu.mutated_lines(head_src, msrc)
        r = review_once(model, requirement, mu.numbered_diff(mu.TARGET, base_src, msrc))
        r["planted_lines"] = planted
        r["caught"], r["hits"] = caught(r["findings"], planted)
        return m.id, r

    results = {}
    with cf.ThreadPoolExecutor(workers) as ex:
        for mid, r in ex.map(job, ([None] if control else []) + list(mutants)):
            results[mid] = r
            status = "UNKNOWN" if r.get("error") else ("caught" if r.get("caught") else ("-" if mid == "control" else "missed"))
            n = len(r["findings"]) if r.get("findings") is not None else "?"
            print(f"   review {mid:<8} {status:<8} findings={n} model={r['model']} attempts={r['attempts']}"
                  + (f"  ERR {r['error'][:90]}" if r.get("error") else ""), flush=True)
    return results


def summarize(mutants: list[mu.Mutant], tests: dict | None, reviews: dict[str, dict]) -> dict:
    rows = []
    for m in mutants:
        row = {"id": m.id, "region": mu.REGION[m.region], "kind": m.kind, "description": m.description}
        if tests:
            row["tests"] = tests.get(m.id, {}).get("status")
        for name, rv in reviews.items():
            row[f"reviewer:{name}"] = (None if rv.get(m.id, {}).get("caught") is None else rv[m.id]["caught"])
        rows.append(row)

    def rate(key, ok):
        # "unknown" (didn't run / didn't answer) is NOT a measurement: never count it as missed.
        vals = [r[key] for r in rows if r.get(key) not in (None, "unknown")]
        return {"caught": sum(1 for v in vals if ok(v)), "measured": len(vals), "planted": len(rows)}

    by_region = {}
    for region in sorted({r["region"] for r in rows}):
        sub = [r for r in rows if r["region"] == region]
        cell = {}
        for k in (["tests"] if tests else []) + [f"reviewer:{n}" for n in reviews]:
            measured = [r for r in sub if r.get(k) not in (None, "unknown")]
            hit = sum(1 for r in measured if r.get(k) in (True, "killed", "killed-by-compiler"))
            cell[k] = f"{hit}/{len(measured)}" + (f" ({len(sub) - len(measured)} unknown)" if len(measured) < len(sub) else "")
        by_region[region] = cell
    summary = {"planted": len(rows), "rows": rows, "by_region": by_region}
    if tests:
        summary["tests"] = rate("tests", lambda v: v in ("killed", "killed-by-compiler"))
        summary["tests_control"] = tests.get("control", {}).get("status")
    for name, rv in reviews.items():
        summary[f"reviewer:{name}"] = rate(f"reviewer:{name}", lambda v: v is True)
        ctl = rv.get("control", {})
        summary[f"reviewer:{name}:control_findings"] = ctl.get("findings")
        summary[f"reviewer:{name}:model"] = ctl.get("model")
    return summary
