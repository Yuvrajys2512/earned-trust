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
    cf_trx = out_dir / "counterfactual" / "head-nofilter.trx"
    if cf_trx.exists():   # PR head with one hunk reverted: which outcomes does that hunk alone cause? (inside the hash)
        import hashlib
        cf = pv.parse_trx(cf_trx)
        ev = out_dir / "counterfactual" / "evidence"
        record["counterfactual"] = {
            "what": "PR head with only the global diagnostic filter reverted (crash fix kept)",
            "trx_sha256": hashlib.sha256(cf_trx.read_bytes()).hexdigest(),
            "outcomes": {t: o.outcome for t, o in cf.items()},
            "failed": {t: o.message for t, o in cf.items() if o.outcome != "Passed"},
            "evidence": {f.name: f.read_text(encoding="utf-8") for f in sorted(ev.glob("*.txt"))} if ev.exists() else {},
        }
        record["checked"].append("Counterfactual: PR head with only the global filter reverted, same tests: "
                                 + ", ".join(f"{t.split('.')[-1]} {o.outcome}" for t, o in cf.items() if "Metadata" in t or "Referenced" in t))
        record.pop("evidence_sha256", None)
        record["evidence_sha256"] = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    tj = ROOT / "out" / "trust.json"
    if tj.exists():   # trust ledger snapshot (Aiven): track record of the regions this PR changes
        import hashlib
        t = json.loads(tj.read_text(encoding="utf-8"))
        src = [f["path"] for f in facts["files"] if f["cls"] == "src"]
        regs = {pth: {k: t["regions"][pth][k] for k in ("state", "why", "human_question_required", "machine_clear_allowed",
                                                       "screeners", "escapes")}
                for pth in src if pth in t["regions"]}
        if regs:
            record["trust"] = {"source": t["source"], "snapshot_at": t["generated_at"], "rule": t["rule"], "regions": regs}
            low = [pth.split("/")[-1] for pth, r in regs.items() if r["human_question_required"]]
            record["checked"].append(f"Trust ledger ({t['source']}): " + "; ".join(
                f"{pth.split('/')[-1]} {r['state']}" for pth, r in regs.items())
                + (f". Human question required for: {', '.join(low)}" if low else ""))
            record.pop("evidence_sha256", None)
            record["evidence_sha256"] = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    qdir = out_dir / "injection"
    if (qdir / "quarantine.json").exists():   # author text, quarantined as data; never an input to the verdict
        import hashlib
        qa = json.loads((qdir / "quarantine.json").read_text(encoding="utf-8")).get("injected")
        naive = None
        for f in sorted(qdir.glob("naive_*.json")):
            n = json.loads(f.read_text(encoding="utf-8"))
            naive = {"model": next((r["model"] for r in n["rows"] if not r.get("error")), None), "summary": n["summary"],
                     "mutants": n["mutants"], "reps": n["reps"], "note": n["note"]}
        if qa:
            record["quarantine"] = {"analysis": {k: qa[k] for k in ("source", "sha256", "chars", "invisible_chars", "verdict",
                                                                    "hidden", "imperatives", "policy")},
                                    "naive": naive}
            record["story_claims"].append({
                "source": "PR description (synthetic; quarantined)",
                "quote": next((h["decoded"] for h in qa["hidden"] if h["kind"] == "html-comment"), qa["hidden"][0]["decoded"] if qa["hidden"] else ""),
                "claim": "the reviewer should report no findings", "verdict": "injection-flagged",
                "why": f"{len(qa['hidden'])} hidden payloads addressed to the reviewer; quoted as data, never followed. "
                       "The verdict above was computed without this text.", "evidence": []})
            record["checked"].append(f"Author text quarantined: {qa['verdict']} ({len(qa['hidden'])} hidden payloads); "
                                     "no model in this pipeline reads it")
            record.pop("evidence_sha256", None)
            record["evidence_sha256"] = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
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


def cmd_inject(args: argparse.Namespace) -> int:
    from . import models, quarantine as qu
    pr = PRS[args.pr]
    out_dir = ROOT / "out" / args.pr / "injection"
    out_dir.mkdir(parents=True, exist_ok=True)
    sd = ROOT / "samples" / "pr_descriptions"
    texts = {"none": None,
             "benign": (sd / f"benign_{args.pr}.md").read_text(encoding="utf-8"),
             "injected": (sd / f"injected_{args.pr}.md").read_text(encoding="utf-8")}
    q = {k: qu.analyze(v, f"samples/pr_descriptions/{k}_{args.pr}.md") for k, v in texts.items() if v is not None}
    (out_dir / "quarantine.json").write_text(json.dumps(q, indent=2, ensure_ascii=False), encoding="utf-8")
    for k, v in q.items():
        print(f"== quarantine {k}: {v['verdict']} ({len(v['hidden'])} hidden/evasive payloads, {len(v['imperatives'])} instruction-like phrases)")
    if args.reviewer:
        model = models.get_reviewer(args.reviewer)
        req = f"{pr.requirement.id}: {pr.requirement.title}" + chr(10) + pr.requirement.summary
        print(f"== naive reviewer {args.reviewer}: {args.mutants} x {list(texts)} x {args.reps}")
        res = qu.naive_experiment(args.repo, pr.base, gf.resolve_branch(args.repo, pr.branch), req, model,
                                  args.mutants, texts, args.reps)
        res["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        (out_dir / f"naive_{args.reviewer}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
        for k, v in res["summary"].items():
            print(f"   {k:<9} caught {v['caught']}/{v['measured']} ({v['unknown']} unknown), findings {v['findings_total']}")
    print(f"   -> {out_dir.relative_to(ROOT)}")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    meta = json.loads((ROOT / "receipts" / "index.json").read_text(encoding="utf-8"))["prs"]
    prs, method = [], []
    load = lambda p: json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    tot = {"files": 0, "human": 0, "naive": 0.0, "human_min": 0.0, "placebo": 0, "agent_tests": 0}
    for key in ["2234", "2297", "2283", "2129"]:
        d = ROOT / "out" / key
        facts, budget, ledger, record = (load(d / n) for n in ("facts.json", "budget.json", "ledger.json", "record.json"))
        if not facts:
            continue
        m = meta.get(key, {})
        links = [{"label": "review page", "href": f"{key}/review.html"}] if (d / "review.html").exists() else []
        if (d / "ai" / "review.html").exists():
            links.append({"label": "AI-written spec", "href": f"{key}/ai/review.html"})
        if (d / "budget.html").exists():
            links.append({"label": "attention budget", "href": f"{key}/budget.html"})
        notes = []
        if record and record.get("human_calibration", {}).get("status") not in (None, "no-drill"):
            notes.append(f"{record['human_calibration']['drills']} human drill on the page (planted bug; the signature records whether it was caught)")
        if record and record.get("quarantine"):
            notes.append(f"PR description quarantined: {record['quarantine']['analysis']['verdict']}")
        if record and record.get("trust"):
            notes.append("Trust ledger: " + "; ".join(f"{p_.split('/')[-1]} {r['state']}" for p_, r in record["trust"]["regions"].items()))
        if record and record.get("time_machine"):
            notes.append(f"Time Machine: {record['time_machine']['verdict']} on {record['time_machine']['bad_commit']}")
        prs.append({"key": key, "requirement": facts["requirement"], "files": len(facts["files"]),
                    "status": m.get("status", "unreviewed"), "headline": m.get("headline", ""), "evidence": m.get("evidence", []),
                    "budget": budget["totals"] if budget else None,
                    "ledger": ledger["counts"] if ledger else None,
                    "record": {"proven": sum(b["status"] == "proven" for b in record["behavior_changes"]),
                               "refusals": len(record["refusals"])} if record else None,
                    "links": links, "notes": notes})
        tot["files"] += len(facts["files"])
        if budget:
            tot["human"] += budget["totals"]["human"]; tot["naive"] += budget["totals"]["naive_minutes"]; tot["human_min"] += budget["totals"]["human_minutes"]
        if ledger:
            # only test methods the PR ADDS (pre-existing tests in the same class are regression checks, not the agent's)
            import re as _re
            pr = PRS[key]
            added = gf.git(args.repo, "diff", "-U0", pr.base, gf.resolve_branch(args.repo, pr.branch), "--", "tests")
            new_methods = set(_re.findall(r"^\+.*?\b(?:Task|void)\s+(\w+)\s*\(", added, _re.M))
            agent = [e for e in ledger["entries"] if not e["test"].startswith("Et") and e["test"].split(".")[-1] in new_methods]
            tot["agent_tests"] += len(agent); tot["placebo"] += sum(e["verdict"] == "placebo" for e in agent)
    method.append(["Files across the PRs with a budget", f"{tot['human']} need a human (~{tot['human_min']:.0f} of ~{tot['naive']:.0f} min)"])
    method.append(["Agent-added tests run on base and head", f"{tot['placebo']} of the {tot['agent_tests']} tests the agents added pass on base too (placebo: prove nothing about the PR)"])
    for key, extra in [("2234", "spec"), ("2297", "spec")]:
        sc = load(ROOT / "out" / key / "spec_compare.json")
        if sc:
            s = sc["summary"]
            method.append([f"#{key}: AI-written spec ({sc['reviewer']}, prompt {sc['prompt_version']}) vs human spec",
                           f"recovered {s['recovered_and_proven']}/{s['human_bcs']} proven changes, {len(s['invented_test_names'])} invented tests, "
                           f"{s['ai_refusals']} vs {s['human_refusals']} refusals"])
    cal = load(ROOT / "out" / "2234" / "calibration.json")
    if cal:
        sm = cal["summary"]
        method.append(["#2234: planted bugs (10) caught by",
                       "; ".join(f"{k.split(':')[-1]} {v['caught']}/{v['measured']}" for k, v in sm.items()
                                 if isinstance(v, dict) and "caught" in v)])
    nv = load(ROOT / "out" / "2234" / "injection" / "naive_gemma.json")
    if nv:
        method.append(["Naive reviewer given the PR text (planted bugs caught)",
                       ", ".join(f"{k}: {v['caught']}/{v['measured']}" for k, v in nv["summary"].items())])
    data = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="minutes"), "prs": prs, "method": method}
    (ROOT / "out" / "index.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    tpl = (Path(__file__).parent / "ui" / "index.html").read_text(encoding="utf-8")
    (ROOT / "out" / "index.html").write_text(tpl.replace("/*INDEX_JSON*/", json.dumps(data).replace("</", "<\\/")), encoding="utf-8")
    for p in prs:
        print(f"   #{p['key']} [{p['status']}] {p['headline'][:100]}")
    for m in method:
        print(f"   {m[0]}: {m[1]}")
    print("   -> out/index.html")
    return 0


def cmd_attest(args: argparse.Namespace) -> int:
    from . import attest as at
    pr = PRS[args.pr]
    ref = gf.resolve_branch(args.repo, pr.branch)
    head = gf.git(args.repo, "rev-parse", ref).strip()
    st = at.attest(args.pr, args.repo, head, pr.branch, Path(args.signed) if args.signed else None)
    if args.signed:   # keep the human's signed record: the trust ledger reads drills from out/<pr>/signoffs/
        import shutil
        dest = ROOT / "out" / args.pr / "signoffs"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.signed, dest / Path(args.signed).name)
        print(f"   signed record kept -> {(dest / Path(args.signed).name).relative_to(ROOT)} (run `et trust` to add its drill)")
    print(f"== attested #{args.pr}: subject {head[:12]}, predicate {at.PREDICATE_TYPE}")
    print(f"   -> {st.relative_to(ROOT)} + .sig (ssh-keygen -Y sign, namespace {at.NAMESPACE}, demo key out/attest/)")
    return cmd_verify(args)


def cmd_verify(args: argparse.Namespace) -> int:
    from . import attest as at
    pr = PRS[args.pr]
    res = at.verify(args.pr, args.repo, gf.resolve_branch(args.repo, pr.branch))
    for c in res["checks"]:
        print(f"   [{'ok' if c['ok'] else 'FAIL'}] {c['check']}: {c['detail'][:140]}")
    print(f"== verify #{args.pr}: {'VALID' if res['ok'] else 'INVALID'}")
    return 0 if res["ok"] else 1


def cmd_trust(args: argparse.Namespace) -> int:
    from . import trust as tr
    events = tr.collect_events()
    regions, records = set(), []
    for key in PRS:
        d = ROOT / "out" / key
        if (d / "facts.json").exists():
            regions |= {f["path"] for f in json.loads((d / "facts.json").read_text(encoding="utf-8"))["files"] if f["cls"] == "src"}
        if (d / "record.json").exists():
            st = d / "attestation" / "statement.json"
            records.append((json.loads((d / "record.json").read_text(encoding="utf-8")),
                            json.loads(st.read_text(encoding="utf-8")) if st.exists() else None))
    source = "local evidence (database not used)"
    n_rec = None
    if not args.local:
        try:
            events, n_rec = tr.sync(events, records)
            source = tr.db_label()
        except Exception as e:   # unreachable DB: say so, compute from local evidence
            print(f"   database unavailable ({type(e).__name__}: {str(e)[:120]}); computing from local evidence", file=sys.stderr)
    ledger = tr.compute(events, sorted(regions))
    snap = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": source,
            "records_stored": n_rec, "events": len(events),
            "rule": f"withdrawn after an escape until {tr.RESTORE_AFTER} later calibrated reviews catch every planted bug "
                    f"(tests >= {int(tr.TESTS_MIN * 100)}%); unknown = no track record = low trust",
            "regions": ledger, "event_rows": events}
    (ROOT / "out" / "trust.json").write_text(json.dumps(snap, indent=2, default=str), encoding="utf-8")
    print(f"== trust ledger: {len(events)} events, {n_rec if n_rec is not None else '-'} records, source: {source}")
    for region, r in ledger.items():
        sc = ", ".join(f"{k} {v['caught']}/{v['caught'] + v['missed']}" for k, v in r["screeners"].items())
        print(f"   {r['state']:<9} {region.split('/')[-1]:<34} {sc[:110]}")
    print("   -> out/trust.json")
    return 0


def cmd_site(args: argparse.Namespace) -> int:
    """Collect the publishable pages + signed evidence into out/site/ (what B8 deploys). Nothing else goes out."""
    import shutil
    site = ROOT / "out" / "site"
    shutil.rmtree(site, ignore_errors=True)
    site.mkdir(parents=True)
    files = ["index.html"]
    for key in PRS:
        for rel in ("review.html", "ai/review.html", "budget.html", "record.json",
                    "attestation/statement.json", "attestation/statement.json.sig"):
            if (ROOT / "out" / key / rel).exists():
                files.append(f"{key}/{rel}")
    if (ROOT / "out" / "attest" / "allowed_signers").exists():
        files.append("attest/allowed_signers")
    for f in files:
        (site / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "out" / f, site / f)
    # Guard: nothing secret-looking may be published.
    from .models import load_env
    load_env()
    secrets = [os.environ[k] for k in ("DATABASE_URL", "GOOGLE_API_KEY", "OPENAI_API_KEY", "NVIDIA_API_KEY") if os.environ.get(k)]
    for f in site.rglob("*"):
        if f.is_file():
            text = f.read_text(encoding="utf-8", errors="ignore")
            leaked = [k for k in secrets if k and k in text] + [m for m in ("avnadmin", "PRIVATE KEY", "postgres://") if m in text]
            if leaked:
                shutil.rmtree(site)
                print(f"REFUSED: {f.relative_to(site)} contains secret-looking content; site removed", file=sys.stderr)
                return 1
    print(f"== site: {len(files)} files, secret scan clean -> {site.relative_to(ROOT)}")
    for f in files:
        print(f"   {f}")
    return 0


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
    p = sub.add_parser("site", help="collect publishable pages + signed evidence into out/site/ (secret-scanned)")
    p.set_defaults(func=cmd_site)
    p = sub.add_parser("trust", help="trust ledger: sync evidence events to Postgres (Aiven), compute per-region trust")
    p.add_argument("--local", action="store_true", help="don't use the database")
    p.set_defaults(func=cmd_trust)
    p = sub.add_parser("attest", help="sign the review record as an in-toto Statement (ssh-keygen -Y sign)")
    p.add_argument("pr", choices=list(PRS))
    p.add_argument("--signed", help="signed record downloaded from the review page (adds the human sign-off)")
    p.set_defaults(func=cmd_attest)
    p = sub.add_parser("verify", help="verify signature, record hash, evidence files and subject commit")
    p.add_argument("pr", choices=list(PRS))
    p.set_defaults(func=cmd_verify)
    p = sub.add_parser("index", help="scoreboard across all PRs -> out/index.html")
    p.set_defaults(func=cmd_index)
    p = sub.add_parser("inject", help="quarantine author text; optionally run the naive reviewer that reads it")
    p.add_argument("pr", choices=["2234"])
    p.add_argument("--reviewer", help="gemma | nemotron | openai (omit: quarantine only)")
    p.add_argument("--mutants", nargs="*", default=["M04", "M06"])
    p.add_argument("--reps", type=int, default=3)
    p.set_defaults(func=cmd_inject)
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
