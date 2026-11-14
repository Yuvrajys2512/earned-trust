"""B6: attestation. The review record becomes a signed, replayable in-toto Statement.

  subject       = the PR head commit (what was reviewed)
  predicateType = https://earned-trust.dev/review/v0.1
  predicate     = the review record (+ the human sign-off, if a signed record from the page is given)
  materials     = every executed evidence file the record relies on, with its SHA-256

Signed with `ssh-keygen -Y sign` (namespace `earned-trust-review`). `verify` checks the signature, that the
record's own evidence hash still matches its content, that every material file still hashes the same,
and that the subject commit is the one git resolves for the branch. Anyone with the repo and our out/
folder can replay it.

The demo key is generated under out/attest/ (gitignored): it shows the mechanism, it is not an identity.
In production the signer is the named human's key (or Sigstore keyless), which is the point of the record.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAMESPACE = "earned-trust-review"
PREDICATE_TYPE = "https://earned-trust.dev/review/v0.1"
IDENTITY = "reviewer@earned-trust.example"
KEY_DIR = ROOT / "out" / "attest"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def record_hash_ok(record: dict) -> tuple[bool, str]:
    r = dict(record)
    claimed = r.pop("evidence_sha256", None)
    body = json.dumps(r, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(body).hexdigest() == claimed, claimed or ""


def materials(pr: str) -> list[dict]:
    out = ROOT / "out" / pr
    globs = ["verify/*.trx", "verify/evidence/**/*.txt", "counterfactual/*.trx", "counterfactual/evidence/*.txt",
             "drills/*.trx", "drills/drill.json", "timemachine/*.trx", "timemachine/github.json",
             "calibration.json", "budget.json", "facts.json", "ledger.json", "injection/quarantine.json",
             "injection/naive_*.json", "regen/regen.json"]
    files = sorted({p for g in globs for p in out.glob(g) if p.is_file()})
    return [{"uri": str(p.relative_to(ROOT)).replace("\\", "/"), "digest": {"sha256": sha256_file(p)}} for p in files]


def ensure_key() -> Path:
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    key = KEY_DIR / "demo_ed25519"
    if not key.exists():
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", IDENTITY, "-f", str(key)], check=True)
    pub = (KEY_DIR / "demo_ed25519.pub").read_text(encoding="utf-8").strip()
    (KEY_DIR / "allowed_signers").write_text(f"{IDENTITY} namespaces=\"{NAMESPACE}\" {pub}\n", encoding="utf-8")
    return key


def attest(pr: str, repo: str, head_commit: str, branch: str, signed_record: Path | None = None) -> Path:
    out = ROOT / "out" / pr
    record = json.loads((out / "record.json").read_text(encoding="utf-8"))
    ok, _ = record_hash_ok(record)
    if not ok:
        raise SystemExit("record.json evidence hash doesn't match its content; rebuild with `et record` first")
    predicate = {"record": record}
    if signed_record:   # the page's download: the human's predictions, decisions, drill result, name
        s = json.loads(signed_record.read_text(encoding="utf-8"))
        if s.get("evidence_sha256") != record["evidence_sha256"]:
            raise SystemExit("signed record was made from a different record (evidence_sha256 differs)")
        predicate["human_signoff"] = {k: s.get(k) for k in ("signoff", "human_calibration", "record_sha256")}
        predicate["human_signoff"]["decisions"] = [{k: b.get(k) for k in ("id", "human_prediction", "prediction_commit_sha256",
                                                                         "revealed_behavior", "match", "decision", "rationale")}
                                                   for b in s.get("behavior_changes", [])]
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": f"git+https://github.com/{record['repo']}@{branch}", "digest": {"gitCommit": head_commit}}],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "requirement": record["requirement"]["id"],
            "base": record["base"],
            "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "evidence_sha256": record["evidence_sha256"],
            "materials": materials(pr),
            **predicate,
        },
    }
    adir = out / "attestation"
    adir.mkdir(parents=True, exist_ok=True)
    st = adir / "statement.json"
    st.write_text(json.dumps(statement, indent=2, ensure_ascii=False), encoding="utf-8")
    key = ensure_key()
    sig = adir / "statement.json.sig"
    sig.unlink(missing_ok=True)
    subprocess.run(["ssh-keygen", "-Y", "sign", "-q", "-f", str(key), "-n", NAMESPACE, str(st)], check=True)
    return st


def verify(pr: str, repo: str, branch_ref: str) -> dict:
    adir = ROOT / "out" / pr / "attestation"
    st, sig = adir / "statement.json", adir / "statement.json.sig"
    checks = []
    with st.open("rb") as fh:
        p = subprocess.run(["ssh-keygen", "-Y", "verify", "-f", str(KEY_DIR / "allowed_signers"), "-I", IDENTITY,
                            "-n", NAMESPACE, "-s", str(sig)], stdin=fh, capture_output=True, text=True)
    checks.append({"check": "signature (ssh-keygen -Y verify)", "ok": p.returncode == 0, "detail": (p.stdout + p.stderr).strip()})
    s = json.loads(st.read_text(encoding="utf-8"))
    rec = s["predicate"]["record"]
    ok, claimed = record_hash_ok(rec)
    checks.append({"check": "record evidence_sha256 matches its content", "ok": ok, "detail": claimed[:16]})
    bad = [m["uri"] for m in s["predicate"]["materials"]
           if not (ROOT / m["uri"]).exists() or sha256_file(ROOT / m["uri"]) != m["digest"]["sha256"]]
    checks.append({"check": f"{len(s['predicate']['materials'])} evidence files re-hashed", "ok": not bad,
                   "detail": "all match" if not bad else f"changed or missing: {bad[:5]}"})
    trx_in_record = {e["trx_sha256"] for b in rec["behavior_changes"] for e in b["evidence"] if e.get("trx_sha256")}
    trx_in_materials = {m["digest"]["sha256"] for m in s["predicate"]["materials"] if m["uri"].endswith(".trx")}
    missing = trx_in_record - trx_in_materials
    checks.append({"check": "every test run the record cites is a signed material", "ok": not missing,
                   "detail": f"{len(trx_in_record)} cited" + (f", {len(missing)} not in materials" if missing else "")})
    head = subprocess.run(["git", "-C", repo, "rev-parse", branch_ref], capture_output=True, text=True).stdout.strip()
    subj = s["subject"][0]["digest"]["gitCommit"]
    checks.append({"check": "subject commit = branch head in the repo", "ok": head == subj, "detail": subj[:12]})
    return {"ok": all(c["ok"] for c in checks), "checks": checks}
