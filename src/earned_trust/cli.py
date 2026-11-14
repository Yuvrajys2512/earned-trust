"""`et` — Earned Trust CLI.

    uv run et facts 2234            # git facts -> out/2234/facts.json
    uv run et facts all
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="et", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=DEFAULT_REPO, help="path to the msgpack clone (default: ../msgpack or $MSGPACK_REPO)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("facts", help="executed git facts for a PR")
    p.add_argument("pr", choices=[*PRS, "all"])
    p.set_defaults(func=cmd_facts)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
