"""Explainable risk router: how much human review a PR gets, decided only by named rules over executed facts.

There is deliberately no score. Each rule either fires or not, names its tier, quotes the fact it fired on and
says where that fact comes from (a git command, an out/ file). The PR's tier is the highest tier any rule sets;
each file also gets a lane, so the signer sees *why* they were asked to read this much and where.

    T0 machine-cleared   proven by byte comparison / consistency check; no human minutes
    T1 light check       human-written but not behavior code (tests, docs): skim for claims
    T2 predict-reveal    behavior code with receipts: the human predicts, then sees the proven changes
    T3 full read         one-way doors, regions whose trust was withdrawn, or behavior with no receipts
"""
from __future__ import annotations

import re

from . import git_facts as gf

TIERS = {"T0": "machine-cleared", "T1": "light check", "T2": "predict-then-reveal", "T3": "full read, required"}
RANK = {t: i for i, t in enumerate(TIERS)}
# Library code users compile against (PublicAPI-tracked or the attributes package). Source generator / analyzer
# internals are not user API; their user-facing contract is the diagnostic list in AnalyzerReleases.*.md.
API_DIRS = ("src/MessagePack.Annotations/", "src/MessagePack/")
PUBLIC_TYPE = re.compile(r"^\+\s*public\s+(?:(?:sealed|static|abstract|partial|readonly)\s+)*"
                         r"(class|interface|struct|enum|record|delegate)\s+(\w+)", re.M)
NEW_DIAG = re.compile(r"^\+(MsgPack\d{3})\s*\|", re.M)
TESTS_MIN = 0.8          # same bar as the trust ledger (trust.TESTS_MIN)
MACHINE_MIN = 0.5        # below this share of machine-cleared files, the budget can't shrink the PR
BEHAVIOR_CLS = ("src", "template")


def public_api(repo: str, base: str, head: str) -> dict:
    """New public surface: added public types in library code, new diagnostic IDs, PublicAPI.*.txt changes."""
    diff = gf.git(repo, "diff", base, head, "--", *API_DIRS)
    types, cur = [], None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
        m = PUBLIC_TYPE.match(line)
        if m and cur and "/PublicAPI." not in cur:
            types.append({"file": cur, "kind": m.group(1), "name": m.group(2)})
    rel = gf.git(repo, "diff", base, head, "--", "*AnalyzerReleases.Unshipped.md", "*AnalyzerReleases.Shipped.md")
    diags = NEW_DIAG.findall(rel)
    rel_files = re.findall(r"^\+\+\+ b/(.+)$", rel, re.M)
    papi = [p for p in gf.git(repo, "diff", "--name-only", base, head, "--", "*PublicAPI.*.txt").split() if p]
    return {"types": types, "diagnostics": diags, "files": sorted({t["file"] for t in types} | set(rel_files) | set(papi)),
            "command": f"git diff {base} {head} -- {' '.join(API_DIRS)} '*AnalyzerReleases.*.md' '*PublicAPI.*.txt'"}


def build(key: str, repo: str, base: str, head: str, facts: dict, *, record: dict | None = None,
          budget: dict | None = None, ledger: dict | None = None, calibration: dict | None = None,
          trust: dict | None = None) -> dict:
    files = facts["files"]
    rules: list[dict] = []
    lanes: dict[str, dict] = {}

    def rule(rid, tier, fired, fact, source, files_=()):
        rules.append({"id": rid, "tier": tier, "fired": bool(fired), "fact": fact, "source": source, "files": list(files_)})
        return fired

    def lane(path, tier, rid):
        cur = lanes.get(path)
        if cur is None or RANK[tier] > RANK[cur["tier"]]:
            lanes[path] = {"tier": tier, "rule": rid}

    # --- T0: machine-cleared by an executed comparison --------------------------------------------------
    cleared = {m["path"]: m for m in (budget or {}).get("machine", [])}
    if budget:
        gen = [p for p, m in cleared.items() if m["cls"] == "generated"]
        tout = [p for p, m in cleared.items() if m["cls"] != "generated"]
        rule("byte-identical-regen", "T0", gen,
             f"{len(gen)} generated files are byte-identical to our own regeneration from the PR's templates",
             f"out/{key}/budget.json (machine lane), out/{key}/regen/regen.json", gen)
        rule("template-output-consistent", "T0", tout,
             f"{len(tout)} template-output files match their templates (T4 check: "
             f"{sum(t['verdict'] == 'consistent' for t in budget.get('t4', []))}/{len(budget.get('t4', []))} consistent)",
             f"out/{key}/budget.json (t4)", tout)
        for p in cleared:
            lane(p, "T0", "byte-identical-regen" if p in gen else "template-output-consistent")
    else:
        rule("byte-identical-regen", "T0", False, "not measured (no attention budget run for this PR)", f"out/{key}/budget.json absent")

    # --- T1: non-behavior files a human still skims ----------------------------------------------------
    light = [f["path"] for f in files if f["path"] not in cleared and f["cls"] not in BEHAVIOR_CLS]
    rule("light-check", "T1", light, f"{len(light)} test/doc files: skim for what they claim (agent tests are checked "
         "on base and head, docs are user-facing claims)", f"out/{key}/facts.json (file classes)", light)
    for p in light:
        lane(p, "T1", "light-check")

    # --- T2: behavior code with receipts -> predict, then reveal ---------------------------------------
    behavior = [f["path"] for f in files if f["path"] not in cleared and f["cls"] in BEHAVIOR_CLS]
    bcs = (record or {}).get("behavior_changes", [])
    proven = [b for b in bcs if b["status"] == "proven"]
    if ledger:
        rule("proven-behavior-change", "T2", proven or behavior,
             f"{len(proven)} behavior changes proven by tests that differ on base vs head "
             f"({', '.join(b['id'] for b in proven) or 'none'}); {len(behavior)} behavior-code files",
             f"out/{key}/ledger.json, out/{key}/record.json", behavior)
        for p in behavior:
            lane(p, "T2", "proven-behavior-change")
    odd = [b for b in proven if b.get("requirement_link") in ("unexplained", "collateral")]
    rule("unrequested-change", "T2", odd,
         ("; ".join(f"{b['id']} {b['requirement_link']}: {b['title']}" for b in odd)
          or ("every proven change is linked to the requirement" if record else "not measured (no review record)")),
         f"out/{key}/record.json (requirement_link)")
    refusals = (record or {}).get("refusals", [])
    rule("refusal", "T2", refusals, ("; ".join(f"{r['id']} \"{r['topic']}\": I won't decide this" for r in refusals)
                                     or ("no refusals" if record else "not measured (no review record)")), f"out/{key}/record.json (refusals)")
    agent = (record or {}).get("ledger_counts", {}).get("agent_tests", {})   # only tests the PR adds (record.py)
    n_agent = sum(agent.values())
    rule("placebo-tests", "T2", agent.get("placebo"),
         f"{agent.get('placebo', 0)} of the {n_agent} agent tests pass on base too (placebo): they don't count as receipts"
         if record else "not measured (agent tests not run on base and head)", f"out/{key}/record.json (ledger_counts.agent_tests)")
    if calibration:
        t = calibration["summary"]["tests"]
        rows = calibration["summary"]["rows"]
        union = sum(r["tests"] == "killed" or any(v is True for k, v in r.items() if k.startswith("reviewer:")) for r in rows)
        rule("screener-below-bar", "T2", t["caught"] / t["measured"] < TESTS_MIN,
             f"tests caught {t['caught']}/{t['measured']} planted bugs (bar {int(TESTS_MIN * 100)}%); all screeners together "
             f"{union}/{len(rows)}: the tests alone can't clear this region", f"out/{key}/calibration.json")
    else:
        rule("screener-below-bar", "T2", False, "not measured (no planted-bug run): an AI reviewer's silence carries no weight here",
             f"out/{key}/calibration.json absent")
    unknown = [p for p, r in ((trust or {}).get("regions") or {}).items()
               if r["state"] == "unknown" and any(f["path"] == p for f in files)]
    rule("no-track-record", "T2", unknown, f"{len(unknown)} changed source regions have no track record in the trust ledger "
         "(unknown = low trust: a human question is required)", "out/trust.json", unknown)

    # --- T3: full read ---------------------------------------------------------------------------------
    api = public_api(repo, base, head)
    if rule("new-public-api", "T3", api["types"] or api["diagnostics"],
            ("adds " + "; ".join([f"public {t['kind']} {t['name']} ({t['file']})" for t in api["types"]]
                                 + ([f"diagnostics {', '.join(api['diagnostics'])} (AnalyzerReleases.Unshipped.md)"]
                                    if api["diagnostics"] else []))
             + ": a one-way door, users will compile against it") if api["types"] or api["diagnostics"]
            else "no new public types, diagnostic IDs or PublicAPI changes", api["command"], api["files"]):
        for p in api["files"]:
            lane(p, "T3", "new-public-api")
    withdrawn = {p: r for p, r in ((trust or {}).get("regions") or {}).items()
                 if r["state"] == "withdrawn" and any(f["path"] == p for f in files)}
    if rule("circuit-breaker", "T3", withdrawn,
            "; ".join(f"{p.split('/')[-1]}: trust withdrawn after {r['escapes'][0]['pr']} escaped "
                      f"({r['escapes'][0]['detail']})" for p, r in withdrawn.items())
            + (f". Stays T3 until trust is earned back: {trust['rule']}" if withdrawn else "")
            if withdrawn else "no changed region has a recorded escape", f"out/trust.json ({(trust or {}).get('source', 'no snapshot')})",
            withdrawn):
        for p in withdrawn:
            lane(p, "T3", "circuit-breaker")
    if rule("no-execution-receipts", "T3", not ledger and behavior,
            f"{len(behavior)} behavior-code files and no base/head test run: behavior is not measured, so nothing can be "
            "shown as proven" if not ledger else "base/head test run exists", f"out/{key}/ledger.json absent" if not ledger
            else f"out/{key}/ledger.json", behavior if not ledger else ()):
        for p in behavior:
            lane(p, "T3", "no-execution-receipts")
    if budget:
        tot = budget["totals"]
        low = tot["machine_cleared"] / tot["files"] < MACHINE_MIN
        rule("machine-clearing-low", "T3", low,
             f"machine clearing covers {tot['machine_cleared']}/{tot['files']} files (bar {int(MACHINE_MIN * 100)}%)"
             + (": mostly hand-written, nothing mechanical to skip" if low else ""), f"out/{key}/budget.json (totals)")

    fired = [r for r in rules if r["fired"]]
    tier = max((r["tier"] for r in fired), key=RANK.get, default="T1")
    lane_files = {t: [p for p, v in lanes.items() if v["tier"] == t] for t in TIERS}
    lines = {f["path"]: f["added"] + f["deleted"] for f in files}
    without_cb = max((r["tier"] for r in fired if r["id"] != "circuit-breaker"), key=RANK.get, default="T1")
    return {
        "pr": key, "base": base, "head": head, "tier": tier, "tier_name": TIERS[tier],
        "policy": "No score. A tier is the highest tier any named rule sets; every rule quotes an executed fact and its source.",
        "why": [f"{r['id']} ({r['tier']}): {r['fact']}" for r in fired if r["tier"] == tier],
        "tier_without_circuit_breaker": without_cb if withdrawn else None,
        "lanes": {t: {"files": len(v), "changed_lines": sum(lines.get(p, 0) for p in v), "paths": v} for t, v in lane_files.items()},
        "rules": rules,
        "tiers": TIERS,
    }
