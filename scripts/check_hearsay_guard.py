"""Negative check: a model-written spec that invents a test, cites the wrong verdict, or cites a
non-existent test in a story claim must come out of the record builder as unproven / unverified.

    uv run python scripts/check_hearsay_guard.py      # needs out/2297/{facts,ledger}.json + receipts/2297/review.ai.json
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from earned_trust import record as rec  # noqa: E402
from earned_trust.prs import PRS  # noqa: E402

out = ROOT / "out" / "2297"
facts = json.loads((out / "facts.json").read_text(encoding="utf-8"))
ledger = json.loads((out / "ledger.json").read_text(encoding="utf-8"))
spec = json.loads((ROOT / "receipts" / "2297" / "review.ai.json").read_text(encoding="utf-8"))

bad = copy.deepcopy(spec)
bad["behavior_changes"][0]["tests"].append("EtCoverageReceiptsTests.Invented_ByModel")   # invented test name
bad["behavior_changes"][1]["expect"] = "catching"                                        # wrong verdict (ledger: broken-by-pr)
bad.setdefault("story_claims", []).append({"source": "test name", "quote": "x", "claim": "x",
                                           "tests": ["Nope.Test"], "verdict": "not-supported", "why": ""})
r = rec.build_record(PRS["2297"], facts, ledger, bad, out / "verify" / "evidence")
status = {b["id"]: b["status"] for b in r["behavior_changes"]}
ok = status["BC-1"] == "unproven" and status["BC-2"] == "unproven" and r["story_claims"][-1]["verdict"] == "unverified"
print(status, r["story_claims"][-1]["verdict"])
print("\n".join(r["hearsay"]))
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
