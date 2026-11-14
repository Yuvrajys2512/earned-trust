"""Prove stage: turn base/head test runs into a behavior ledger.

A test is evidence of a behavior change only if it FAILS on the base commit and
PASSES on the PR head ("catching test"). A test that passes on both is a
*placebo* for this PR: it may be a fine regression test, but it proves nothing
about what the PR changed. "Didn't run" is *unknown*, never *pass* (F-15).

Input: TRX files named `<side>-<project>.trx` (side = base|head) in a run dir,
as written by scripts/verify_2234_base.sh. Output: a ledger dict.
"""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path

NS = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}

VERDICTS = {
    ("Failed", "Passed"): "catching",   # proven behavior change
    ("Passed", "Passed"): "placebo",    # passes before and after: proves nothing about this PR
    ("Passed", "Failed"): "broken-by-pr",
    ("Failed", "Failed"): "failing-both",
}


@dataclass
class TestOutcome:
    outcome: str            # Passed | Failed | NotRun | Missing
    message: str = ""       # first lines of the failure message, if any
    trx: str = ""
    trx_sha256: str = ""


@dataclass
class LedgerEntry:
    id: str
    test: str
    project: str
    verdict: str
    base: TestOutcome
    head: TestOutcome
    signal: str = ""        # short, human-readable reason (from the base failure)
    tags: list[str] = field(default_factory=list)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def short_name(test: str) -> str:
    """`Ns.Sub.Class.Method` -> `Class.Method` (xUnit names differ by whether the class has a namespace)."""
    parts = test.split("(")[0].split(".")
    return ".".join(parts[-2:]) if len(parts) > 2 else test


def parse_trx(path: Path) -> dict[str, TestOutcome]:
    digest = sha256(path)
    root = ET.parse(path).getroot()
    out: dict[str, TestOutcome] = {}
    for r in root.iterfind(".//t:Results/t:UnitTestResult", NS):
        msg_el = r.find("t:Output/t:ErrorInfo/t:Message", NS)
        msg = (msg_el.text or "") if msg_el is not None else ""
        out[short_name(r.get("testName", "?"))] = TestOutcome(
            outcome=r.get("outcome", "?"),
            message="\n".join(msg.replace("\r", "").splitlines()[:12]),
            trx=path.name,
            trx_sha256=digest,
        )
    return out


# Signals we recognise in a base-side failure; they turn a stack dump into one line.
SIGNALS = [
    (re.compile(r"AD0001: Analyzer '([^']+)' threw an exception of type '([^']+)' with message '([^']*)'"),
     lambda m: f"analyzer crash on base: {m.group(2).split('.')[-1]}: {m.group(3)}", "analyzer-crash"),
    (re.compile(r"Mismatch between number of diagnostics returned, expected \"(\d+)\" actual \"(\d+)\""),
     lambda m: f"diagnostic count differs on base (expected {m.group(1)}, got {m.group(2)})", "diagnostics"),
    (re.compile(r"GENERATOR THREW: (\w+): ([^\r\n]*)"),
     lambda m: f"source generator crash on base: {m.group(1)}: {m.group(2)}", "generator-crash"),
    (re.compile(r"error CS\d+"), lambda m: "test does not compile on base", "compile"),
]


def explain(msg: str) -> tuple[str, list[str]]:
    hits, tags = [], []
    for rx, fmt, tag in SIGNALS:
        m = rx.search(msg)
        if m:
            hits.append(fmt(m))
            tags.append(tag)
    return ("; ".join(hits) or (msg.splitlines()[0] if msg else "")), tags


def build_ledger(run_dir: Path) -> dict:
    sides: dict[str, dict[str, dict[str, TestOutcome]]] = {"base": {}, "head": {}}
    for trx in sorted(run_dir.glob("*.trx")):
        side, _, project = trx.stem.partition("-")
        if side in sides:
            sides[side][project] = parse_trx(trx)

    entries: list[LedgerEntry] = []
    projects = sorted(set(sides["base"]) | set(sides["head"]))
    for project in projects:
        b, h = sides["base"].get(project, {}), sides["head"].get(project, {})
        for test in sorted(set(b) | set(h)):
            bo = b.get(test, TestOutcome("Missing"))
            ho = h.get(test, TestOutcome("Missing"))
            verdict = VERDICTS.get((bo.outcome, ho.outcome), "unknown")
            signal, tags = explain(bo.message) if verdict == "catching" else ("", [])
            entries.append(LedgerEntry("", test, project, verdict, bo, ho, signal, tags))

    order = {"catching": 0, "broken-by-pr": 1, "unknown": 2, "failing-both": 3, "placebo": 4}
    entries.sort(key=lambda e: (order.get(e.verdict, 9), e.project, e.test))
    for i, e in enumerate(entries, 1):
        e.id = f"T-{i:02d}"

    counts: dict[str, int] = {}
    for e in entries:
        counts[e.verdict] = counts.get(e.verdict, 0) + 1
    return {
        "method": "run each test on BASE (+ only the PR's test files) and on HEAD; "
                  "catching = fails on base & passes on head",
        "run_dir": str(run_dir),
        "counts": counts,
        "entries": [asdict(e) for e in entries],
    }
