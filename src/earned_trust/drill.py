"""B3: human drill (two-sided calibration, "Threat Image Projection" for the human).

The AI reviewer and the tests are measured on planted bugs (calibrate.py). The human is measured
too: one predict-then-reveal question is a *drill*, built from a planted mutant whose behavior was
executed. The page discloses up front that one question is a drill, and reveals which one only after
the human has decided. A missed drill (accepted the planted bug) flags the signature.

Evidence: the drill test (receipts/<pr>/drills/EtDrillTests.cs) runs on the PR head and on the head
with the mutant planted; the generator output of both runs is the reveal. Nothing is described that
wasn't executed.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

from . import calibrate as cal
from . import mutate as mu
from .prove import parse_trx

ROOT = Path(__file__).resolve().parents[2]
TEST_DEST = "tests/MessagePack.SourceGenerator.Tests"
FILTER = "FullyQualifiedName~EtDrillTests"


def _run(worktree: Path, label: str, out_dir: Path, env: dict) -> dict:
    trx = out_dir / f"{label}.trx"
    trx.unlink(missing_ok=True)
    ev = out_dir / label
    env = {**env, "ET_EVIDENCE_DIR": str(ev)}
    cmd = [env.get("ET_DOTNET", "dotnet"), "test", cal.TEST_PROJECT, "--filter", FILTER, "--logger", f"trx;LogFileName={trx}"]
    t0 = time.time()
    p = subprocess.run(cmd, cwd=worktree, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    (out_dir / f"{label}.log").write_text(p.stdout + p.stderr, encoding="utf-8")
    outcomes = parse_trx(trx) if trx.exists() else {}
    o = next(iter(outcomes.values()), None)
    evf = ev / "drill-mixed-middle.txt"
    return {"outcome": o.outcome if o else "NoResult", "seconds": round(time.time() - t0),
            "message": (o.message if o and hasattr(o, "message") else None),
            "trx_sha256": hashlib.sha256(trx.read_bytes()).hexdigest() if trx.exists() else None,
            "generated": evf.read_text(encoding="utf-8") if evf.exists() else None}


def run(worktree: Path, pr: str, mutant_id: str) -> dict:
    out_dir = ROOT / "out" / pr / "drills"
    out_dir.mkdir(parents=True, exist_ok=True)
    src_test = ROOT / "receipts" / pr / "drills" / "EtDrillTests.cs"
    dest_test = worktree / TEST_DEST / src_test.name
    shutil.copyfile(src_test, dest_test)
    target = worktree / mu.TARGET
    original = target.read_bytes()
    m = next(x for x in mu.MUTANTS if x.id == mutant_id)
    env = cal.dotnet_env()
    try:
        head = _run(worktree, "head", out_dir, env)
        text = original.decode("utf-8")
        crlf = cal.CRLF in text
        src, _ = mu.apply(text.replace(cal.CRLF, cal.LF), m)
        target.write_bytes((src.replace(cal.LF, cal.CRLF) if crlf else src).encode("utf-8"))
        mutant = _run(worktree, mutant_id, out_dir, env)
    finally:
        target.write_bytes(original)
        dest_test.unlink(missing_ok=True)
    return {"mutant": {"id": m.id, "kind": m.kind, "description": m.description, "region": mu.REGION[m.region]},
            "test": "EtDrillTests.Drill_MixedKeyInTheMiddle_LaterMembersStillSerialized",
            "head": head, "planted": mutant,
            "verdict": "executed: head passes, planted fails" if head["outcome"] == "Passed" and mutant["outcome"] != "Passed"
                       else f"UNEXPECTED: head {head['outcome']}, planted {mutant['outcome']}"}
