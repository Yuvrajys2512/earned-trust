"""B7: trust ledger. Trust is earned per code region, from executed evidence, and withdrawn after an escape.

Events (one row per executed screener outcome, idempotent by event_key):
  planted    a known bug planted in the region; did the screener (tests / AI reviewer) catch it?   (calibrate)
  escape     a real bug in the region got past every gate and reached users                       (time machine)
  backtest   a screener replayed on the commit that introduced an escape                          (time machine)
  drill      a human drill on a signed review: did the named human catch the planted bug?           (signed record)
  injection  the AI reviewer re-measured with author text in its prompt (naive pipeline foil)      (et inject)

Rule (stated, deterministic, in code below):
  - a region with an escape is WITHDRAWN until it collects RESTORE_AFTER later calibrated reviews whose planted
    bugs were all caught by at least one screener AND whose test suite caught >= TESTS_MIN of them. Time alone
    never restores trust.
  - a region with planted-bug data and no escape is MEASURED (shown with its catch rates).
  - a region with no data is UNKNOWN, and treated like WITHDRAWN: no track record is not a good track record.
  - WITHDRAWN or UNKNOWN -> every change there gets a human question; no file there may be machine-cleared.

Storage: Aiven Postgres (DATABASE_URL) is the system of record; `out/trust.json` is an exported snapshot so the
pages work offline. If the database is unreachable the ledger is computed from local evidence and says so.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TC = "src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs"
RESTORE_AFTER = 3
TESTS_MIN = 0.8

SCHEMA = """
create table if not exists et_events (
  event_key text primary key,
  at timestamptz not null,
  pr text not null,
  region text not null,
  subregion text,
  screener text not null,
  kind text not null check (kind in ('planted','escape','backtest','drill','injection')),
  outcome text not null,
  detail text,
  evidence_uri text,
  evidence_sha256 text
);
create table if not exists et_records (
  evidence_sha256 text primary key,
  pr text not null,
  head text not null,
  requirement text not null,
  record jsonb not null,
  statement jsonb,
  attested boolean not null default false,
  stored_at timestamptz not null default now()
);
create index if not exists et_events_region on et_events(region);
"""


def _sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT)).replace("\\", "/")


def collect_events() -> list[dict]:
    """Every event comes from a file we executed and hashed; nothing is typed in by hand."""
    ev: list[dict] = []
    cal_p = ROOT / "out" / "2234" / "calibration.json"
    if cal_p.exists():
        cal = json.loads(cal_p.read_text(encoding="utf-8"))
        at = cal.get("generated_at")
        for r in cal["summary"]["rows"]:
            for scr, val in r.items():
                if scr != "tests" and not scr.startswith("reviewer:"):
                    continue
                outcome = ("caught" if val in (True, "killed", "killed-by-compiler") else
                           "unknown" if val in (None, "unknown") else "missed")
                ev.append({"event_key": f"planted:2234:{r['id']}:{scr}", "at": at, "pr": "#2234 (agent PR)", "region": TC,
                           "subregion": f"GetObjectInfo/{r['region']}", "screener": scr, "kind": "planted", "outcome": outcome,
                           "detail": f"{r['id']} {r['description']}", "evidence_uri": _rel(cal_p), "evidence_sha256": _sha(cal_p)})
    tm_p = ROOT / "out" / "2234" / "timemachine" / "timemachine.json"
    gh_p = ROOT / "out" / "2234" / "timemachine" / "github.json"
    if tm_p.exists() and gh_p.exists():
        tm = json.loads(tm_p.read_text(encoding="utf-8"))
        gh = json.loads(gh_p.read_text(encoding="utf-8"))
        pr, issue = gh["pr"]["value"], gh["issue"]["value"]
        ev.append({"event_key": f"escape:{tm['bad_commit']}", "at": issue["created_at"], "pr": "upstream #2106", "region": TC,
                   "subregion": "GetObjectInfo", "screener": "merge gate", "kind": "escape", "outcome": "escaped",
                   "detail": f"commit {tm['bad_commit']} merged {pr['merged_at'][:10]} by its author with "
                             f"{len(gh['reviews']['value'])} reviews; reported by a user {issue['created_at'][:10]} (issue #2234)",
                   "evidence_uri": _rel(gh_p), "evidence_sha256": _sha(gh_p)})
        ev.append({"event_key": f"backtest:{tm['bad_commit']}:agent-tests-2234", "at": tm["generated_at"], "pr": "upstream #2106",
                   "region": TC, "subregion": "GetObjectInfo", "screener": "tests (agent #2234 tests, replayed)", "kind": "backtest",
                   "outcome": "caught" if tm["verdict"] == "would-have-caught" else "missed",
                   "detail": f"{len(tm['caught_by'])} tests red on {tm['bad_commit']}", "evidence_uri": _rel(tm_p),
                   "evidence_sha256": _sha(tm_p)})
    nv_p = ROOT / "out" / "2234" / "injection" / "naive_gemma.json"
    if nv_p.exists():
        nv = json.loads(nv_p.read_text(encoding="utf-8"))
        for r in nv["rows"]:
            if r["condition"] != "injected":
                continue
            ev.append({"event_key": f"injection:2234:{r['mutant']}:{r['rep']}", "at": nv.get("generated_at"), "pr": "#2234 (agent PR)",
                       "region": TC, "subregion": r["mutant"], "screener": "reviewer:gemma + injected PR text", "kind": "injection",
                       "outcome": "unknown" if r["caught"] is None else ("caught" if r["caught"] else "missed"),
                       "detail": f"{r['mutant']} rep {r['rep']}, findings={len(r['findings']) if r['findings'] is not None else '?'}",
                       "evidence_uri": _rel(nv_p), "evidence_sha256": _sha(nv_p)})
    for sp in sorted((ROOT / "out").glob("*/signoffs/*.json")):   # signed records saved from the review page
        s = json.loads(sp.read_text(encoding="utf-8"))
        for d in (s.get("human_calibration") or {}).get("results", []):
            ev.append({"event_key": f"drill:{s.get('record_sha256', sp.stem)}:{d['id']}", "at": s["signoff"]["timestamp"],
                       "pr": s["requirement"]["id"], "region": TC, "subregion": d["mutant"],
                       "screener": f"human:{s['signoff']['name']}", "kind": "drill",
                       "outcome": "caught" if d["caught"] else "missed", "detail": f"decision {d['decision']}",
                       "evidence_uri": _rel(sp), "evidence_sha256": _sha(sp)})
    return ev


def compute(events: list[dict], regions: list[str]) -> dict:
    by_region: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        by_region[e["region"]].append(e)
    out = {}
    for region in sorted(set(regions) | set(by_region)):
        evs = by_region.get(region, [])
        stats: dict[str, dict] = {}
        for e in evs:
            if e["kind"] not in ("planted", "drill", "injection", "backtest"):
                continue
            s = stats.setdefault(f"{e['screener']}" + (" [injected]" if e["kind"] == "injection" else ""),
                                 {"kind": e["kind"], "caught": 0, "missed": 0, "unknown": 0})
            s[e["outcome"] if e["outcome"] in ("caught", "missed") else "unknown"] += 1
        escapes = sorted((e for e in evs if e["kind"] == "escape"), key=lambda e: e["at"])
        # calibrated reviews after the last escape: per PR, union of screeners caught every planted bug, tests >= TESTS_MIN
        last = escapes[-1]["at"] if escapes else None
        per_pr: dict[str, dict] = defaultdict(lambda: {"mutants": defaultdict(list), "tests": []})
        for e in evs:
            if e["kind"] == "planted" and (last is None or (e["at"] or "") > last):
                per_pr[e["pr"]]["mutants"][e["detail"].split()[0]].append(e["outcome"] == "caught")
                if e["screener"] == "tests" and e["outcome"] != "unknown":
                    per_pr[e["pr"]]["tests"].append(e["outcome"] == "caught")
        qualifying = []
        for pr, d in per_pr.items():
            union = all(any(v) for v in d["mutants"].values())
            tests_rate = sum(d["tests"]) / len(d["tests"]) if d["tests"] else 0
            qualifying.append({"pr": pr, "union_all_caught": union, "tests_rate": round(tests_rate, 2),
                               "counts": union and tests_rate >= TESTS_MIN})
        n_ok = sum(q["counts"] for q in qualifying)
        if escapes and n_ok < RESTORE_AFTER:
            state = "withdrawn"
            why = (f"{len(escapes)} escape(s): {escapes[-1]['detail']}. Restored only after {RESTORE_AFTER} later calibrated "
                   f"reviews with every planted bug caught and tests >= {int(TESTS_MIN * 100)}%; so far {n_ok} "
                   f"({'; '.join(f'{q['pr']}: union {q['union_all_caught']}, tests {int(q['tests_rate'] * 100)}%' for q in qualifying) or 'none'}).")
        elif stats:
            state, why = "measured", "Planted-bug results below; no escape recorded."
        else:
            state, why = "unknown", "No track record in this region. Treated as low trust: no track record is not a good one."
        out[region] = {"state": state, "why": why, "human_question_required": state in ("withdrawn", "unknown"),
                       "machine_clear_allowed": state == "measured", "screeners": stats,
                       "escapes": [{k: e[k] for k in ("at", "pr", "detail", "evidence_uri")} for e in escapes],
                       "calibrated_reviews_since_escape": qualifying, "events": len(evs)}
    return out


# ------------------------------------------------------------------ storage

def _connect():
    import psycopg
    from .models import load_env
    load_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg.connect(url, connect_timeout=15)


def db_label() -> str:
    from urllib.parse import urlparse
    from .models import load_env
    load_env()
    u = urlparse(os.environ.get("DATABASE_URL", ""))
    host = u.hostname or "?"
    return f"Aiven PostgreSQL ({host.split('.')[0][:6]}…{'.aivencloud.com' if 'aivencloud' in host else ''})"   # never the credentials


def sync(events: list[dict], records: list[tuple[dict, dict | None]]) -> list[dict]:
    """Upsert events + records into Postgres; read every event back (the DB is the source of truth)."""
    from psycopg.types.json import Jsonb
    with _connect() as c:
        c.execute(SCHEMA)
        for e in events:
            c.execute("""insert into et_events (event_key, at, pr, region, subregion, screener, kind, outcome, detail, evidence_uri, evidence_sha256)
                         values (%(event_key)s, %(at)s, %(pr)s, %(region)s, %(subregion)s, %(screener)s, %(kind)s, %(outcome)s, %(detail)s, %(evidence_uri)s, %(evidence_sha256)s)
                         on conflict (event_key) do update set outcome = excluded.outcome, detail = excluded.detail,
                           at = excluded.at, evidence_sha256 = excluded.evidence_sha256""",
                      {**e, "at": e["at"] or datetime.now(timezone.utc).isoformat()})
        for rec, st in records:
            c.execute("""insert into et_records (evidence_sha256, pr, head, requirement, record, statement, attested)
                         values (%s, %s, %s, %s, %s, %s, %s) on conflict (evidence_sha256) do update
                         set statement = excluded.statement, attested = excluded.attested""",
                      (rec["evidence_sha256"], rec["requirement"]["id"], rec["head"], rec["requirement"]["id"],
                       Jsonb(rec), Jsonb(st) if st else None, st is not None))
        rows = c.execute("""select event_key, at, pr, region, subregion, screener, kind, outcome, detail, evidence_uri, evidence_sha256
                            from et_events order by at""").fetchall()
        n_rec = c.execute("select count(*) from et_records").fetchone()[0]
    cols = ["event_key", "at", "pr", "region", "subregion", "screener", "kind", "outcome", "detail", "evidence_uri", "evidence_sha256"]
    out = [dict(zip(cols, r)) for r in rows]
    for e in out:
        e["at"] = e["at"].isoformat() if hasattr(e["at"], "isoformat") else e["at"]
    return out, n_rec
