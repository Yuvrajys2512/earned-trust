"""`et` — Earned Trust CLI.

    uv run et facts 2234            # git facts -> out/2234/facts.json
    uv run et facts all
    uv run et prove 2234            # TRX runs -> out/2234/ledger.json (add --run to re-run tests)
    uv run et record 2234           # facts + ledger + receipts/2234/review.json -> record.json + review.html
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
    record = rec.build_record(pr, facts, ledger, spec, out_dir / "verify" / "evidence")
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
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
