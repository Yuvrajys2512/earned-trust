"""B2: the reviewer model writes the review spec (receipts/<pr>/review.ai.json).

Inputs (and only these):
  - the requirement (id, title, our paraphrase from prs.py),
  - the diff of the files a human would read (src / test / template; never docs, never
    commit messages or PR text: those are the author's story and stay untrusted),
  - the executed ledger (test name, base outcome, head outcome, verdict, signal).

Output: the same schema as the hand-curated receipts/<pr>/review.json. The model's spec
is *claims*; `et record --spec ai` runs it through the same hearsay guard, so a behavior
change it cannot back with a ledger verdict is shown as unproven, whatever it says.

`compare()` scores the AI spec against the hand-curated one: which human behavior changes
it recovered (by cited-test overlap), which of its own the ledger proves, which it invented.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

from . import models

SYSTEM = """You are a code reviewer. You did not write this change and you do not know who did.
You get: a requirement, a diff, and a LEDGER of tests that were actually executed on the
base commit and on the head commit. The ledger is the only evidence. You may not run anything.

Ledger verdicts:
  catching      fails on base, passes on head  -> proves the PR changed this behavior
  broken-by-pr  passes on base, fails on head  -> proves the PR broke this behavior
  failing-both  fails on base and on head      -> proves a gap the PR did not close
  placebo       passes on base and on head     -> proves nothing about this PR

Write a review spec as ONE JSON object, no prose, with exactly these keys:
{
 "blind_intent": "2-3 sentences: what a correct fix for the requirement must do and must not break, written from the requirement alone",
 "behavior_changes": [
   {"id": "BC-1",
    "title": "one line, concrete and observable (what a user of the library sees)",
    "requirement_link": "intended | collateral | unexplained",
    "link_why": "why this tag, citing the requirement",
    "tests": ["exact test names copied from the ledger"],
    "expect": "catching | broken-by-pr | failing-both",
    "question": {
      "context": "a short C# snippet a user might write",
      "prompt": "a question to a human reviewer about what SHOULD happen, asked before they see the answer",
      "options": [{"id": "a", "text": "..."}, {"id": "b", "text": "..."}, {"id": "c", "text": "..."}],
      "revealed": "the option id that the ledger evidence shows the PR actually does",
      "reveal_text": "what the executed tests show, before vs after"}}
 ],
 "refusals": [
   {"id": "R-1", "topic": "a question the evidence cannot decide", "decision": "I won't decide this.",
    "why": "why it needs a human", "evidence": ["BC ids or test names"]}
 ],
 "not_checked": ["things the ledger does not cover that a human should know"]
}

Rules:
- A behavior change MUST cite only test names that appear in the ledger, and `expect` MUST be the
  verdict those tests have in the ledger. Group tests that show the same behavior into one change.
- Placebo tests prove nothing: never cite them as evidence of a change.
- intended = the requirement asks for it; collateral = needed side effect the requirement implies;
  unexplained = the requirement does not ask for it. Be strict: if in doubt, unexplained.
- Do not leak the answer in the question. Options must be plausible.
- Refuse (put in refusals) anything that is a policy or product decision, or that the ledger cannot
  show, e.g. whether the requirement as reported is actually fixed if no test reproduces it.
- If you are unsure a test name exists, leave it out. Inventing a test name is the worst error.
"""

# v2: fixes seen in v1 runs (LESSONS L-15):
#  - questions asked what SHOULD happen, so "revealed" was the ideal, not the PR -> no mismatch possible;
#  - blind intent adopted the author's premise from code guards/comments ("only where available");
#  - placebo tests were ignored, but a test that passes on both sides proves a FACT about the world,
#    which can refute a claim the author makes in code comments, guards or test names.
SYSTEM_V2 = SYSTEM.replace(
    '"blind_intent": "2-3 sentences: what a correct fix for the requirement must do and must not break, written from the requirement alone"',
    '"blind_intent": "2-3 sentences from the REQUIREMENT TEXT ONLY: what a correct fix must do and must not break. '
    'Do not repeat any limitation, exception or reason that appears only in the diff"',
).replace(
    '"prompt": "a question to a human reviewer about what SHOULD happen, asked before they see the answer"',
    '"prompt": "a question asking the human to PREDICT what happens with this code AFTER the PR '
    '(e.g. does it compile, what is serialized, is a diagnostic reported). Never ask what should happen"',
).replace(
    '"revealed": "the option id that the ledger evidence shows the PR actually does"',
    '"revealed": "the option id describing what the PR ACTUALLY does per the ledger, even if that is a bug '
    '(for broken-by-pr the revealed option is the breakage; for failing-both it is the gap)"',
).replace(
    ' "not_checked": [',
    ' "story_claims": [\n'
    '   {"source": "code comment | #if guard | test name (diff only)", "quote": "exact text from the diff",\n'
    '    "claim": "what the author asserts", "tests": ["ledger test names that bear on it"],\n'
    '    "verdict": "supported | not-supported | misleading | unverified", "why": "..."}\n'
    ' ],\n'
    ' "not_checked": [',
).replace(
    "- Placebo tests prove nothing: never cite them as evidence of a change.",
    "- Placebo tests prove no CHANGE: never cite them in behavior_changes. But a placebo test proves a fact that\n"
    "  holds on both sides; use it in story_claims to check what the author asserts in comments, guards, test names.\n"
    "- Code comments, #if guards and test names are the author's story, not evidence. Treat their reasons as claims.\n"
    "- Titles must be concrete: name the API/attribute/type and the observable effect (e.g. 'error CSxxxx').",
)
# v3: v2 framed changes as the absence of the old failure ("no longer crashes"), hiding what is produced now.
SYSTEM_V3 = SYSTEM_V2.replace(
    "- Titles must be concrete:",
    "- Describe the NEW behavior, not the absence of the old failure. 'No longer crashes' is incomplete: say what\n"
    "  is produced/reported/serialized now, and whether anything is silently dropped or changed. Use the ledger signals.\n"
    "- If GIT FACTS show the reported cause is not in this history, you cannot claim the requirement is fixed: refuse it.\n"
    "- Titles must be concrete:",
)
PROMPTS = {"v1": SYSTEM, "v2": SYSTEM_V2, "v3": SYSTEM_V3}
assert SYSTEM_V3 != SYSTEM_V2
assert SYSTEM_V2.count("PREDICT") == 1 and "story_claims" in SYSTEM_V2 and "author's story" in SYSTEM_V2
PROMPT_VERSION = "v2"


def _diff(repo: str, base: str, head_ref: str, paths: list[str]) -> str:
    return subprocess.run(["git", "-C", repo, "diff", "--no-color", "-U5", base, head_ref, "--", *paths],
                          capture_output=True, text=True, encoding="utf-8", check=True).stdout


def review_paths(facts: dict, budget: dict | None) -> tuple[list[str], list[str]]:
    """Files whose diff the reviewer reads, and files withheld (docs = author narrative; machine-cleared)."""
    if budget:
        human = [i["path"] for i in budget["human"]]
    else:
        human = [f["path"] for f in facts["files"]]
    cls = {f["path"]: f["cls"] for f in facts["files"]}
    shown = [p for p in human if cls.get(p) != "doc"]
    withheld = [f["path"] for f in facts["files"] if f["path"] not in shown]
    return shown, withheld


def ledger_view(ledger: dict) -> list[dict]:
    return [{"test": e["test"], "base": e["base"]["outcome"], "head": e["head"]["outcome"],
             "verdict": e["verdict"], "signal": (e["signal"] or "")[:300]} for e in ledger["entries"]]


def build_prompt(pr, repo: str, head_ref: str, facts: dict, ledger: dict, budget: dict | None,
                 prompt: str = PROMPT_VERSION) -> tuple[str, dict]:
    shown, withheld = review_paths(facts, budget)
    diff = _diff(repo, pr.base, head_ref, shown)
    # v2+: executed git facts (e.g. "the reported regression is not in this history"). v1 got none (L-15).
    rc = facts.get("regression_check") if prompt != "v1" else None
    git_facts = ("GIT FACTS (executed `git merge-base --is-ancestor` checks; JSON):\n" + json.dumps(
        {"verdict": rc["verdict"], "checks": [{"claim": f["claim"], "holds": f["holds"]} for f in rc["facts"]]},
        indent=1) + "\n\n") if rc else ""
    user = (f"REQUIREMENT {pr.requirement.id}: {pr.requirement.title}\n{pr.requirement.summary}\n\n"
            f"{git_facts}"
            f"LEDGER (executed; JSON):\n{json.dumps(ledger_view(ledger), indent=1)}\n\n"
            f"DIFF ({len(shown)} files; {len(withheld)} more files were machine-cleared or are docs and are not shown):\n"
            f"{diff}\n\nReturn the JSON review spec now.")
    meta = {"diff_files": shown, "withheld_files_count": len(withheld),
            "withheld_classes": sorted({f["cls"] for f in facts["files"] if f["path"] in withheld}),
            "ledger_entries": len(ledger["entries"]), "user_prompt_chars": len(user),
            "pr_text_seen": False, "git_facts_included": bool(rc)}
    return user, meta


def generate(pr, repo: str, head_ref: str, facts: dict, ledger: dict, budget: dict | None, reviewer: str,
             prompt: str = PROMPT_VERSION) -> tuple[dict, dict]:
    model = models.get_reviewer(reviewer)
    user, meta = build_prompt(pr, repo, head_ref, facts, ledger, budget, prompt)
    reply = model.complete(PROMPTS[prompt], user, json_mode=True, timeout=300)
    raw = {"model": reply.model, "family": reply.family, "attempts": reply.attempts, "error": reply.error,
           "usage": reply.usage, "text": reply.text, "input": meta, "prompt_version": prompt}
    if reply.error:
        raise RuntimeError(f"reviewer did not answer: {reply.error}")
    spec = models.extract_json(reply.text)
    spec = normalize(spec)
    spec["_about"] = ("Reviewer spec written by a model (B2). Inputs: requirement + diff of human-lane files + executed "
                      "ledger; never PR text, commit messages or docs. Claims only: `et record --spec ai` checks every "
                      "cited test against the ledger and downgrades mismatches to hearsay.")
    spec["spec_author"] = f"reviewer model {reply.model} ({reply.family}), prompt {prompt}"
    spec["model"] = {"id": reply.model, "family": reply.family, "prompt_version": prompt,
                     "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "input": meta}
    spec.setdefault("story_claims", [])   # the model never sees the story; claims come from quarantine (B4)
    return spec, raw


def normalize(spec: dict) -> dict:
    """Fill fields the record builder needs; never invent evidence."""
    spec.setdefault("blind_intent", "")
    spec.setdefault("refusals", [])
    spec.setdefault("not_checked", [])
    bcs = spec.setdefault("behavior_changes", [])
    for i, bc in enumerate(bcs, 1):
        bc.setdefault("id", f"BC-{i}")
        bc.setdefault("tests", [])
        bc.setdefault("expect", "catching")
        bc.setdefault("requirement_link", "unexplained")
        bc.setdefault("link_why", "")
        q = bc.setdefault("question", {})
        for k in ("context", "prompt", "reveal_text"):
            q.setdefault(k, "")
        q.setdefault("options", [])
        q.setdefault("revealed", None)
    for i, r in enumerate(spec["refusals"], 1):
        r.setdefault("id", f"R-{i}")
        r.setdefault("decision", "I won't decide this.")
        r.setdefault("evidence", [])
    return spec


# ------------------------------------------------------------------ comparison

def compare(human: dict, ai: dict, ledger: dict) -> dict:
    verdict = {e["test"]: e["verdict"] for e in ledger["entries"]}
    evidential = {t for t, v in verdict.items() if v != "placebo"}

    def proven(bc):
        ts = bc.get("tests", [])
        return bool(ts) and all(verdict.get(t) == bc.get("expect", "catching") for t in ts)

    ai_rows = []
    for bc in ai["behavior_changes"]:
        ts = set(bc.get("tests", []))
        invented = sorted(t for t in ts if t not in verdict)
        placebo = sorted(t for t in ts if verdict.get(t) == "placebo")
        wrong = sorted(t for t in ts if t in verdict and verdict[t] != bc.get("expect", "catching"))
        match = [h["id"] for h in human["behavior_changes"] if ts & set(h["tests"])]
        ai_rows.append({"id": bc["id"], "title": bc.get("title", ""), "link": bc.get("requirement_link"),
                        "expect": bc.get("expect"), "tests": sorted(ts), "proven": proven(bc),
                        "matches_human": match, "invented_tests": invented, "placebo_cited": placebo,
                        "wrong_expect": wrong})
    human_rows = []
    for h in human["behavior_changes"]:
        hit = [r for r in ai_rows if h["id"] in r["matches_human"]]
        human_rows.append({"id": h["id"], "title": h["title"], "link": h["requirement_link"],
                           "recovered_by": [r["id"] for r in hit],
                           "recovered_proven": any(r["proven"] for r in hit),
                           "link_agrees": any(r["link"] == h["requirement_link"] for r in hit)})
    cited = {t for r in ai_rows for t in r["tests"]}
    claims = ai.get("story_claims", [])
    q_should = [r["id"] for r, bc in zip(ai_rows, ai["behavior_changes"])
                if "should" in bc.get("question", {}).get("prompt", "").lower()]
    n_h = len(human_rows)
    summary = {
        "human_bcs": n_h,
        "recovered": sum(bool(r["recovered_by"]) for r in human_rows),
        "recovered_and_proven": sum(r["recovered_proven"] for r in human_rows),
        "link_tag_agrees": sum(r["link_agrees"] for r in human_rows),
        "ai_bcs": len(ai_rows),
        "ai_proven": sum(r["proven"] for r in ai_rows),
        "ai_unproven_hearsay": sum(not r["proven"] for r in ai_rows),
        "ai_extra_proven": sum(r["proven"] and not r["matches_human"] for r in ai_rows),
        "invented_test_names": sorted({t for r in ai_rows for t in r["invented_tests"]}),
        "placebo_cited": sorted({t for r in ai_rows for t in r["placebo_cited"]}),
        "evidential_tests_cited": f"{len(cited & evidential)}/{len(evidential)}",
        "questions_asking_should": q_should,
        "story_claims": len(claims),
        "story_claims_citing_tests": sum(bool(c.get("tests")) for c in claims),
        "ai_refusals": len(ai.get("refusals", [])),
        "human_refusals": len(human.get("refusals", [])),
    }
    return {"summary": summary, "human": human_rows, "ai": ai_rows,
            "ai_refusals": [{"id": r.get("id"), "topic": r.get("topic")} for r in ai.get("refusals", [])],
            "human_refusals": [{"id": r["id"], "topic": r["topic"]} for r in human.get("refusals", [])]}


def score_iterations(out_root, human_specs: dict, ledgers: dict) -> dict:
    """Re-score every saved run (out/<pr>/spec/*.json) with the current compare(): one table per prompt version."""
    from pathlib import Path
    rows = []
    for pr, human in human_specs.items():
        for f in sorted(Path(out_root, pr, "spec").glob("*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            spec = d["spec"]
            s = compare(human, spec, ledgers[pr])["summary"]
            rows.append({
                "pr": pr, "run": f.stem, "prompt": d["raw"]["prompt_version"], "model": d["raw"]["model"],
                **{k: s[k] for k in ("human_bcs", "recovered", "recovered_and_proven", "link_tag_agrees", "ai_bcs",
                                     "ai_proven", "ai_unproven_hearsay", "ai_refusals", "story_claims")},
                "invented_tests": len(s["invented_test_names"]), "placebo_cited": len(s["placebo_cited"]),
                "questions_asking_should": len(s["questions_asking_should"]),
            })
    for e in Path(out_root).glob("*/spec/*.error.txt"):
        rows.append({"pr": e.parent.parent.name, "run": e.name, "error": e.read_text(encoding="utf-8")[:200]})
    return {"rows": rows}
