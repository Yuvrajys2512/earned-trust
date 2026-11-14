"""`et` — Earned Trust CLI.

    uv run et facts 2234            # git facts -> out/2234/facts.json
    uv run et facts all
    uv run et prove 2234            # TRX runs -> out/2234/ledger.json (add --run to re-run tests)
    uv run et record 2234           # facts + ledger + receipts/2234/review.json -> record.json + review.html
    uv run et calibrate 2234 --tests            # planted bugs vs the test suite (local dotnet)
    uv run et calibrate 2234 --reviewer gemma   # planted bugs vs the AI reviewer
    uv run et budget 2297           # machine-cleared vs human files (needs scripts/regen_2297.sh first)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import git_facts as gf
from . import prove as pv
from . import record as rec
from .prs import PRS

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPO = os.environ.get("MSGPACK_REPO", str(ROOT.parent / "msgpack"))


def cmd_facts(args: argparse.Namespace) -> int:
    keys = list(PRS) if args.pr == "all" else [args.pr]
    for key in keys:
        pr = PRS[key]
        head_ref = gf.resolve_branch(args.repo, pr.branch)
        head = gf.git(args.repo, "rev-parse", "--short=8", head_ref).strip()
        parent = gf.git(args.repo, "rev-parse", "--short=8", f"{head_ref}~1").strip()
        files = gf.changed_files(args.repo, pr.base, head_ref)
        facts: dict = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "requirement": {"id": pr.requirement.id, "title": pr.requirement.title, "url": pr.requirement.url},
            "base": pr.base,
            "head": head,
            "head_parent_is_base": parent.startswith(pr.base[:8]),
            "files": [gf.to_dict(f) for f in files],
            "file_classes": dict(Counter(f.cls for f in files)),
        }
        if pr.requirement.regressed_between:
            good, bad = pr.requirement.regressed_between
            touched = [f.path for f in files if f.cls == "src"]
            facts["regression_check"] = gf.to_dict(gf.regression_check(args.repo, pr.base, good, bad, touched))

        out = ROOT / "out" / key / "facts.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(facts, indent=2), encoding="utf-8")

        print(f"== {pr.requirement.id} {pr.branch} {pr.base}..{head}  ({len(files)} files)")
        print("   classes:", ", ".join(f"{k}={v}" for k, v in sorted(facts["file_classes"].items())))
        if "regression_check" in facts:
            print("   regression:", facts["regression_check"]["verdict"])
        print(f"   -> {out.relative_to(ROOT)}")
    return 0


def cmd_prove(args: argparse.Namespace) -> int:
    run_dir = ROOT / "out" / args.pr / "verify"
    if args.run:
        import subprocess
        script = ROOT / "scripts" / f"verify_{args.pr}_base.sh"
        rc = subprocess.run(["bash", str(script), args.repo]).returncode
        if rc:
            print(f"verify script exited {rc}", file=sys.stderr)
    if not any(run_dir.glob("*.trx")):
        print(f"no TRX files in {run_dir}; run with --run", file=sys.stderr)
        return 1
    ledger = pv.build_ledger(run_dir)
    ledger["run_dir"] = str(run_dir.relative_to(ROOT))
    out = ROOT / "out" / args.pr / "ledger.json"
    out.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    print(f"== ledger {args.pr}: " + ", ".join(f"{k}={v}" for k, v in ledger["counts"].items()))
    for e in ledger["entries"]:
        print(f"   {e['id']} {e['verdict']:<13} {e['test']}")
        if e["signal"]:
            print(f"        {e['signal']}")
    print(f"   -> {out.relative_to(ROOT)}")
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    import re
    pr = PRS[args.pr]
    out_dir = ROOT / "out" / args.pr
    facts = json.loads((out_dir / "facts.json").read_text(encoding="utf-8"))
    ledger = json.loads((out_dir / "ledger.json").read_text(encoding="utf-8"))
    spec = json.loads((ROOT / "receipts" / args.pr / "review.json").read_text(encoding="utf-8"))
    run_log = ROOT / "out" / f"verify_{args.pr}_run.log"
    if run_log.exists():
        m = re.search(r"SDK (\d+\.\d+\.\d+)", run_log.read_text(encoding="utf-8", errors="replace"))
        if m:
            ledger["toolchain"] = {"dotnet_sdk": m.group(1), "note": "global.json overridden to SDK 9 in worktrees (L-04)"}
    cal_path = out_dir / "calibration.json"
    calibration = json.loads(cal_path.read_text(encoding="utf-8")) if cal_path.exists() else None
    record = rec.build_record(pr, facts, ledger, spec, out_dir / "verify" / "evidence", calibration)
    (out_dir / "record.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    tpl = (Path(__file__).parent / "ui" / "review.html").read_text(encoding="utf-8")
    embedded = json.dumps(record).replace("</", "<\\/")
    (out_dir / "review.html").write_text(tpl.replace("/*RECORD_JSON*/", embedded), encoding="utf-8")
    print(f"== record {pr.requirement.id}: {len(record['behavior_changes'])} behavior changes "
          f"({sum(b['status'] == 'proven' for b in record['behavior_changes'])} proven), "
          f"{len(record['refusals'])} refusals, {len(record['hearsay'])} hearsay")
    print(f"   evidence_sha256 {record['evidence_sha256']}")
    print(f"   -> {(out_dir / 'record.json').relative_to(ROOT)}, {(out_dir / 'review.html').relative_to(ROOT)}")
    return 0


def cmd_calibrate(args: argparse.Namespace) -> int:
    from . import calibrate as cal, models, mutate as mu
    pr = PRS[args.pr]
    out_dir = ROOT / "out" / args.pr
    path = out_dir / "calibration.json"
    raw_dir = out_dir / "calibration"
    raw_dir.mkdir(parents=True, exist_ok=True)

    def save_raw(key: str, value: dict) -> None:   # one file per run: parallel runs can't clobber each other
        f = raw_dir / f"{key.replace(':', '_').replace('#', '-')}.json"
        if args.only and f.exists():               # partial rerun: merge into the earlier run
            old = json.loads(f.read_text(encoding="utf-8"))["data"]
            # never replace a real answer with "no answer" (unknown is not newer evidence)
            value = {k: v for k, v in value.items() if not (v.get("error") and k in old and not old[k].get("error"))}
            value = {**old, **value}
        f.write_text(json.dumps({"key": key, "data": value}, indent=2), encoding="utf-8")
    mutants = [m for m in mu.MUTANTS if not args.only or m.id in args.only]
    run_control = not args.only or "control" in args.only
    if args.tests:
        wt = Path(os.environ.get("WT_ROOT", str(Path(args.repo).parent / "msgpack-wt"))) / f"{args.pr}-head"
        print(f"== tests vs {len(mutants)} mutants in {wt}")
        save_raw("tests", cal.run_tests_on_mutants(wt, out_dir / "mutants", mutants))
    for name in args.reviewer:
        model = models.get_reviewer(name)
        req = f"{pr.requirement.id}: {pr.requirement.title}" + chr(10) + pr.requirement.summary
        head_ref = gf.resolve_branch(args.repo, pr.branch)
        for i in range(args.repeat):
            key = name if args.repeat == 1 else f"{name}#{i + 1}"
            print(f"== reviewer {key} ({model.models[0]}) vs {len(mutants)} mutants + control")
            save_raw(f"reviewer:{key}", cal.run_reviewer_on_mutants(args.repo, pr.base, head_ref, req, model, mutants, control=run_control))
    data = {"raw": {}}
    if path.exists():  # legacy single-file layout
        data["raw"].update(json.loads(path.read_text(encoding="utf-8")).get("raw", {}))
    for f in sorted(raw_dir.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        data["raw"][d["key"]] = d["data"]
    reviews = {k.split(":", 1)[1]: v for k, v in data["raw"].items() if k.startswith("reviewer:")}
    # Re-score stored findings with the current matcher (no new model calls), so every run is judged by one rule.
    head_src = cal.git_show(args.repo, gf.resolve_branch(args.repo, pr.branch), mu.TARGET)
    for rv in reviews.values():
        for m in mu.MUTANTS:
            if m.id in rv:
                rv[m.id]["planted_lines"] = mu.mutated_lines(head_src, mu.apply(head_src, m)[0])
                rv[m.id]["caught"], rv[m.id]["hits"] = cal.caught(rv[m.id].get("findings"), rv[m.id]["planted_lines"])
    data["summary"] = cal.summarize(mu.MUTANTS, data["raw"].get("tests"), reviews)
    data["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    sm = data["summary"]
    for k, v in sm.items():
        if isinstance(v, dict) and "caught" in v:
            print(f"   {k:<22} caught {v['caught']}/{v['measured']} measured ({v['planted']} planted)")
    print("   by region:", json.dumps(sm["by_region"]))
    print(f"   -> {path.relative_to(ROOT)}")
    return 0


def cmd_budget(args: argparse.Namespace) -> int:
    from . import budget as bd
    pr = PRS[args.pr]
    out_dir = ROOT / "out" / args.pr
    facts = json.loads((out_dir / "facts.json").read_text(encoding="utf-8"))
    regen_path = out_dir / "regen" / "regen.json"
    regen = json.loads(regen_path.read_text(encoding="utf-8")) if regen_path.exists() else None
    if regen is None and facts["file_classes"].get("generated"):
        print(f"note: no {regen_path.relative_to(ROOT)}; generated files stay in the human lane", file=sys.stderr)
    head = gf.resolve_branch(args.repo, pr.branch)
    result = bd.build(args.repo, pr.base, head, facts, regen)
    result["requirement"] = facts["requirement"]
    ledger_path = out_dir / "ledger.json"
    if ledger_path.exists():  # executed base/head outcomes: what the human's minutes should go to first
        lg = json.loads(ledger_path.read_text(encoding="utf-8"))
        result["ledger"] = {"counts": lg["counts"], "entries": [
            {k: e[k] for k in ("id", "test", "verdict", "signal")} for e in lg["entries"]]}
    result["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = out_dir / "budget.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    tpl = (Path(__file__).parent / "ui" / "budget.html").read_text(encoding="utf-8")
    (out_dir / "budget.html").write_text(tpl.replace("/*BUDGET_JSON*/", json.dumps(result).replace("</", "<\\/")), encoding="utf-8")
    t = result["totals"]
    print(f"== budget {pr.requirement.id}: {t['files']} files -> {t['machine_cleared']} machine-cleared, {t['human']} human")
    print(f"   minutes (estimate): naive {t['naive_minutes']} -> human {t['human_minutes']}")
    for r in result["t4"]:
        print(f"   T4 {r['verdict']:<12} {r['template']}")
    for i in result["human"]:
        print(f"   {i['cumulative_minutes']:>5} min  {i['cls']:<15} {i['path']}  ({i['why']})")
    print(f"   -> {out.relative_to(ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="et", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=DEFAULT_REPO, help="path to the msgpack clone (default: ../msgpack or $MSGPACK_REPO)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("facts", help="executed git facts for a PR")
    p.add_argument("pr", choices=[*PRS, "all"])
    p.set_defaults(func=cmd_facts)
    p = sub.add_parser("prove", help="base/head test outcomes -> behavior ledger")
    p.add_argument("pr", choices=list(PRS))
    p.add_argument("--run", action="store_true", help="re-run scripts/verify_<pr>_base.sh first")
    p.set_defaults(func=cmd_prove)
    p = sub.add_parser("record", help="build the review record + HTML review page")
    p.add_argument("pr", choices=list(PRS))
    p.set_defaults(func=cmd_record)
    p = sub.add_parser("calibrate", help="plant bugs in the PR's changed code; measure tests and AI reviewers")
    p.add_argument("pr", choices=list(PRS))
    p.add_argument("--tests", action="store_true", help="run the test suite against each mutant (local dotnet)")
    p.add_argument("--reviewer", action="append", default=[], help="gemma | nemotron | openai (repeatable)")
    p.add_argument("--repeat", type=int, default=1, help="reviewer runs per mutant (models are stochastic)")
    p.add_argument("--only", nargs="*", help="mutant ids, e.g. M01 M08")
    p.set_defaults(func=cmd_calibrate)
    p = sub.add_parser("budget", help="attention budget: which files a machine clears, which a human reads")
    p.add_argument("pr", choices=list(PRS))
    p.set_defaults(func=cmd_budget)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
