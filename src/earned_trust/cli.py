"""`et` — Earned Trust CLI.

    uv run et facts 2234            # git facts -> out/2234/facts.json
    uv run et facts all
    uv run et prove 2234            # TRX runs -> out/2234/ledger.json (add --run to re-run tests)
    uv run et record 2234           # facts + ledger + receipts/2234/review.json -> record.json + review.html
    uv run et calibrate 2234 --tests            # planted bugs vs the test suite (local dotnet)
    uv run et calibrate 2234 --reviewer gemma   # planted bugs vs the AI reviewer
    uv run et timemachine 2234      # replay on the commit that caused the bug (scripts/timemachine_2234.sh first)
    uv run et spec 2297 --reviewer gemma --runs 3   # B2: the model writes the review spec
    uv run et record 2297 --spec ai                 # same hearsay guard -> out/2297/ai/
    uv run et budget 2297          # machine-cleared vs human files (needs scripts/regen_2297.sh first)
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
    spec_name = "review.json" if args.spec == "human" else "review.ai.json"
    spec = json.loads((ROOT / "receipts" / args.pr / spec_name).read_text(encoding="utf-8"))
    dest = out_dir if args.spec == "human" else out_dir / "ai"   # the AI-spec record never overwrites the human one
    dest.mkdir(parents=True, exist_ok=True)
    run_log = ROOT / "out" / f"verify_{args.pr}_run.log"
    if run_log.exists():
        m = re.search(r"SDK (\d+\.\d+\.\d+)", run_log.read_text(encoding="utf-8", errors="replace"))
        if m:
            ledger["toolchain"] = {"dotnet_sdk": m.group(1), "note": "global.json overridden to SDK 9 in worktrees (L-04)"}
    cal_path = out_dir / "calibration.json"
    calibration = json.loads(cal_path.read_text(encoding="utf-8")) if cal_path.exists() else None
    bud_path = out_dir / "budget.json"
    budget = json.loads(bud_path.read_text(encoding="utf-8")) if bud_path.exists() else None
    dr_spec = ROOT / "receipts" / args.pr / "drills.json"
    dr_run = out_dir / "drills" / "drill.json"
    drills = json.loads(dr_spec.read_text(encoding="utf-8")) if dr_spec.exists() else None
    drill_run = json.loads(dr_run.read_text(encoding="utf-8")) if dr_run.exists() else None
    record = rec.build_record(pr, facts, ledger, spec, out_dir / "verify" / "evidence", calibration, budget,
                              drills, drill_run)
    tm_path = out_dir / "timemachine" / "timemachine.json"
    if tm_path.exists():   # executed backtest on the commit that caused the bug; covered by the record hash
        import hashlib
        record["time_machine"] = json.loads(tm_path.read_text(encoding="utf-8"))
        record["checked"].append(
            f"Time Machine: the agent's tests replayed on {record['time_machine']['parent']} -> "
            f"{record['time_machine']['bad_commit']} (the commit that caused the bug): {record['time_machine']['verdict']}")
        record.pop("evidence_sha256", None)
        body = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
        record["evidence_sha256"] = hashlib.sha256(body).hexdigest()
    (dest / "record.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    tpl = (Path(__file__).parent / "ui" / "review.html").read_text(encoding="utf-8")
    embedded = json.dumps(record).replace("</", "<\\/")
    (dest / "review.html").write_text(tpl.replace("/*RECORD_JSON*/", embedded), encoding="utf-8")
    print(f"== record {pr.requirement.id}: {len(record['behavior_changes'])} behavior changes "
          f"({sum(b['status'] == 'proven' for b in record['behavior_changes'])} proven), "
          f"{len(record['refusals'])} refusals, {len(record['hearsay'])} hearsay")
    for h in record["hearsay"]:
        print(f"   hearsay: {h}")
    print(f"   evidence_sha256 {record['evidence_sha256']}")
    print(f"   -> {(dest / 'record.json').relative_to(ROOT)}, {(dest / 'review.html').relative_to(ROOT)}")
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
    head = gf.git(args.repo, "rev-parse", "--short=8", gf.resolve_branch(args.repo, pr.branch)).strip()
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


def cmd_spec(args: argparse.Namespace) -> int:
    from . import spec as sp
    pr = PRS[args.pr]
    out_dir = ROOT / "out" / args.pr
    facts = json.loads((out_dir / "facts.json").read_text(encoding="utf-8"))
    ledger = json.loads((out_dir / "ledger.json").read_text(encoding="utf-8"))
    bud_path = out_dir / "budget.json"
    budget = json.loads(bud_path.read_text(encoding="utf-8")) if bud_path.exists() else None
    human = json.loads((ROOT / "receipts" / args.pr / "review.json").read_text(encoding="utf-8"))
    head_ref = gf.resolve_branch(args.repo, pr.branch)
    raw_dir = out_dir / "spec"
    raw_dir.mkdir(parents=True, exist_ok=True)
    print(f"== spec {pr.requirement.id}: reviewer {args.reviewer}, prompt {args.prompt}, {args.runs} run(s)")
    runs, best = [], None
    for i in range(1, args.runs + 1):
        tag = f"{args.reviewer}-{args.prompt}-{i}"
        try:
            spec, raw = sp.generate(pr, args.repo, head_ref, facts, ledger, budget, args.reviewer, args.prompt)
        except Exception as e:   # no answer / no JSON is "unknown", recorded as such, never "clean"
            (raw_dir / f"{tag}.error.txt").write_text(f"{type(e).__name__}: {e}", encoding="utf-8")
            print(f"   run {i}: no spec ({type(e).__name__}: {str(e)[:200]})")
            runs.append({"run": tag, "error": f"{type(e).__name__}: {e}"})
            continue
        cmp_ = sp.compare(human, spec, ledger)
        (raw_dir / f"{tag}.json").write_text(json.dumps({"raw": raw, "spec": spec, "compare": cmp_}, indent=2), encoding="utf-8")
        s = cmp_["summary"]
        print(f"   run {i} ({spec['model']['id']}): recovered {s['recovered']}/{s['human_bcs']} human BCs "
              f"({s['recovered_and_proven']} proven, {s['link_tag_agrees']} same tag), AI BCs {s['ai_proven']}/{s['ai_bcs']} proven, "
              f"invented tests {len(s['invented_test_names'])}, placebo cited {len(s['placebo_cited'])}, "
              f"refusals {s['ai_refusals']}")
        runs.append({"run": tag, "summary": s})
        score = (s["recovered_and_proven"], s["ai_proven"] - s["ai_unproven_hearsay"])
        if best is None or score > best[0]:
            best = (score, tag, spec, cmp_)
    if best is None:
        return 1
    _, tag, spec, cmp_ = best
    spec["model"]["selected_run"] = tag
    spec["model"]["runs"] = len(runs)
    (ROOT / "receipts" / args.pr / "review.ai.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    out = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "reviewer": args.reviewer,
           "prompt_version": args.prompt, "selected_run": tag,
           "selection_rule": "most human BCs recovered with proof, then fewest unproven; every run is listed",
           "runs": runs, **cmp_}
    (out_dir / "spec_compare.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"   -> receipts/{args.pr}/review.ai.json (run {tag}), out/{args.pr}/spec_compare.json")
    return 0


def cmd_spec_score(args: argparse.Namespace) -> int:
    from . import spec as sp
    prs = [p for p in PRS if (ROOT / "out" / p / "spec").exists() and (ROOT / "receipts" / p / "review.json").exists()]
    human = {p: json.loads((ROOT / "receipts" / p / "review.json").read_text(encoding="utf-8")) for p in prs}
    ledgers = {p: json.loads((ROOT / "out" / p / "ledger.json").read_text(encoding="utf-8")) for p in prs}
    res = sp.score_iterations(ROOT / "out", human, ledgers)
    res["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (ROOT / "out" / "spec_iterations.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    cols = ["recovered_and_proven", "link_tag_agrees", "ai_proven", "ai_bcs", "invented_tests", "placebo_cited",
            "questions_asking_should", "story_claims", "ai_refusals"]
    print("pr    run              " + " ".join(c[:10].rjust(10) for c in cols))
    for r in sorted(res["rows"], key=lambda r: (r["pr"], r["run"])):
        if "error" in r:
            print(f"{r['pr']:<5} {r['run']:<16} no answer: {r['error'][:80]}")
        else:
            print(f"{r['pr']:<5} {r['run']:<16} " + " ".join(str(r[c]).rjust(10) for c in cols))
    print("   -> out/spec_iterations.json")
    return 0


def cmd_drill(args: argparse.Namespace) -> int:
    from . import drill as dr
    wt = Path(os.environ.get("WT_ROOT", str(Path(args.repo).parent / "msgpack-wt"))) / f"{args.pr}-head"
    print(f"== drill {args.pr}: {args.mutant} planted in {wt}")
    res = dr.run(wt, args.pr, args.mutant)
    res["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = ROOT / "out" / args.pr / "drills" / "drill.json"
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"   head: {res['head']['outcome']}   planted {args.mutant}: {res['planted']['outcome']}   -> {res['verdict']}")
    print(f"   -> {out.relative_to(ROOT)}")
    return 0 if res["verdict"].startswith("executed") else 1


TIME_MACHINE = {"2234": {"pr": 2106, "issue": 2234, "bad": "1a74a620"}}


def cmd_timemachine(args: argparse.Namespace) -> int:
    from . import timemachine as tm
    cfg = TIME_MACHINE[args.pr]
    run_dir = ROOT / "out" / args.pr / "timemachine"
    if not any(run_dir.glob("base-*.trx")):
        print(f"no runs in {run_dir.relative_to(ROOT)}; run scripts/timemachine_{args.pr}.sh first", file=sys.stderr)
        return 1
    parent = gf.git(args.repo, "rev-parse", "--short=8", cfg["bad"] + "^").strip()
    res = tm.build(run_dir, cfg["pr"], cfg["issue"], cfg["bad"], parent)
    res["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = run_dir / "timemachine.json"
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    h = res["history"]
    print(f"== time machine #{cfg['issue']}: {parent} -> {cfg['bad']}  verdict: {res['verdict']}")
    print(f"   upstream PR #{cfg['pr']}: {h['pr'].get('title')!r}  author={h['pr'].get('author')} "
          f"merged_by={h['pr'].get('merged_by')} reviews={h['review_count']}")
    print(f"   issue opened {h['issue'].get('created_at')} ({h['issue'].get('state')})")
    for e in res["entries"]:
        print(f"   {e['verdict']:<13} {e['test']}")
        print(f"        parent: {e['parent']:<6} {e['parent_says']}")
        print(f"        bad:    {e['bad_commit']:<6} {e['bad_commit_says']}")
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
    p.add_argument("--spec", choices=["human", "ai"], default="human",
                   help="ai: use receipts/<pr>/review.ai.json and write out/<pr>/ai/")
    p.set_defaults(func=cmd_record)
    p = sub.add_parser("calibrate", help="plant bugs in the PR's changed code; measure tests and AI reviewers")
    p.add_argument("pr", choices=list(PRS))
    p.add_argument("--tests", action="store_true", help="run the test suite against each mutant (local dotnet)")
    p.add_argument("--reviewer", action="append", default=[], help="gemma | nemotron | openai (repeatable)")
    p.add_argument("--repeat", type=int, default=1, help="reviewer runs per mutant (models are stochastic)")
    p.add_argument("--only", nargs="*", help="mutant ids, e.g. M01 M08")
    p.set_defaults(func=cmd_calibrate)
    p = sub.add_parser("spec", help="the reviewer model writes the review spec (never sees PR text)")
    p.add_argument("pr", choices=list(PRS))
    p.add_argument("--reviewer", default="gemma", help="gemma | nemotron | openai")
    p.add_argument("--runs", type=int, default=1, help="independent runs (models are stochastic)")
    p.add_argument("--prompt", default="v2", help="prompt version (see spec.PROMPTS)")
    p.set_defaults(func=cmd_spec)
    p = sub.add_parser("drill", help="execute the human drill: drill test on head and on head + planted mutant")
    p.add_argument("pr", choices=["2234"])
    p.add_argument("--mutant", default="M04")
    p.set_defaults(func=cmd_drill)
    p = sub.add_parser("spec-score", help="re-score every saved spec run per prompt version")
    p.set_defaults(func=cmd_spec_score)
    p = sub.add_parser("timemachine", help="replay the factory on the commit that caused the reported bug")
    p.add_argument("pr", choices=list(TIME_MACHINE))
    p.set_defaults(func=cmd_timemachine)
    p = sub.add_parser("budget", help="attention budget: which files a machine clears, which a human reads")
    p.add_argument("pr", choices=list(PRS))
    p.set_defaults(func=cmd_budget)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
