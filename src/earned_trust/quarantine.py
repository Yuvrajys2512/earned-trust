"""B4: quarantine for untrusted author text (PR descriptions, commit messages, READMEs).

Our pipeline never feeds this text to a model as instructions: the spec writer and the reviewer
get requirement + diff + executed evidence only (P4). Quarantine exists so the *human* sees what
the text hides, quoted as data:

  - HTML comments (invisible when rendered as Markdown),
  - zero-width / bidi control characters (invisible; split words to defeat keyword filters),
  - Unicode tag characters U+E0000-E007F (invisible ASCII smuggling),
  - imperative text addressed to a reviewer / AI ("report no findings", "pre-approved", ...),
    searched after normalising all of the above, so hiding doesn't help.

Detection is regex, stdlib only, deterministic. It can miss things; that's fine, because nothing
downstream depends on it catching them (the verdict never reads this text).
"""
from __future__ import annotations

import hashlib
import re
import unicodedata

ZERO_WIDTH = "​‌‍‎‏⁠⁡⁢⁣⁤﻿"
BIDI = "‪‫‬‭‮⁦⁧⁨⁩"
HTML_COMMENT = re.compile(r"<!--(.*?)-->", re.S)
TAG_RUN = re.compile("[\U000E0000-\U000E007F]+")

IMPERATIVES = [
    (r"\b(ai|llm|automated)?\s*review(er|ers)?\b\s*[:,-]", "addresses the reviewer directly"),
    (r"\b(note|instruction)s?\s+(to|for)\s+(the\s+)?(ai|llm|reviewers?|assistant)", "addresses the reviewer directly"),
    (r"\b(report|return|output)\s+(no|zero|an empty( list of)?)\s+(findings|issues|comments)", "tells the reviewer to report nothing"),
    (r"\{\s*\"findings\"\s*:\s*\[\s*\]\s*\}", "supplies the reviewer's answer"),
    (r"\b(pre-?approved|already\s+(been\s+)?approved|approved\s+by\s+(the\s+)?(security|maintainers?))", "claims prior approval"),
    (r"\b(do\s+not|don't|never)\s+(report|mention|flag)", "tells the reviewer to suppress something"),
    (r"\b(treat|consider|mark)\b.{0,60}\b(as\s+)?(approved|intended|safe|low\s+severity)", "pre-decides the verdict"),
    (r"\bignore\s+(all\s+|any\s+)?(previous|prior|above)\s+instructions", "instruction override"),
    (r"\bsafe\s+to\s+merge\b", "pre-decides the verdict"),
]


def _strip(text: str) -> str:
    return "".join(c for c in text if c not in ZERO_WIDTH and c not in BIDI)


def analyze(text: str, source: str) -> dict:
    flags = []
    for m in HTML_COMMENT.finditer(text):
        flags.append({"kind": "html-comment", "hidden": True, "offset": m.start(),
                      "decoded": _strip(m.group(1)).strip()})
    for m in TAG_RUN.finditer(text):
        flags.append({"kind": "unicode-tag-chars", "hidden": True, "offset": m.start(), "chars": len(m.group(0)),
                      "decoded": "".join(chr(ord(c) - 0xE0000) for c in m.group(0)).strip()})
    zw = [i for i, c in enumerate(text) if c in ZERO_WIDTH]
    bidi = [i for i, c in enumerate(text) if c in BIDI]
    if zw:
        # report each line that carries zero-width chars, with the text they split
        for ln in text.splitlines():
            if any(c in ZERO_WIDTH for c in ln):
                flags.append({"kind": "zero-width-chars", "hidden": False, "evades_filters": True,
                              "note": "readable by a human, but split so keyword filters miss it",
                              "chars": sum(c in ZERO_WIDTH for c in ln),
                              "decoded": _strip(ln).strip()})
    if bidi:
        flags.append({"kind": "bidi-controls", "hidden": True, "chars": len(bidi)})

    # What a human sees when it's rendered: no comments, no invisible characters.
    visible = TAG_RUN.sub("", HTML_COMMENT.sub("", text))
    visible = "".join(c for c in visible if c not in ZERO_WIDTH and c not in BIDI)
    visible = re.sub(r"\n{3,}", "\n\n", visible).strip()
    # What a model sees: everything. Search the normalised full text for instructions.
    normalised = _strip(TAG_RUN.sub(lambda m: "".join(chr(ord(c) - 0xE0000) for c in m.group(0)), text))
    normalised = unicodedata.normalize("NFKC", normalised)
    imperatives = []
    for pat, why in IMPERATIVES:
        for m in re.finditer(pat, normalised, re.I):
            lo = normalised.rfind("\n", 0, m.start()) + 1
            hi = normalised.find("\n", m.end())
            line = normalised[lo:hi if hi != -1 else None].strip()
            in_hidden = m.group(0).lower() not in visible.lower()   # a human reading the rendered text can't see it
            imperatives.append({"match": m.group(0), "why": why, "line": line, "hidden": in_hidden})
    hidden = [f for f in flags if f.get("hidden") or f.get("evades_filters")]
    verdict = ("injection-suspected" if imperatives and (hidden or len(imperatives) > 1)
               else "hidden-content" if hidden else "instruction-like" if imperatives else "clean")
    return {
        "source": source,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "chars": len(text),
        "visible_chars": len(visible),
        "invisible_chars": len(zw) + len(bidi) + sum(f.get("chars", 0) for f in flags if f["kind"] == "unicode-tag-chars"),
        "verdict": verdict,
        "hidden": hidden,
        "imperatives": imperatives,
        "visible_text": visible,
        "policy": "Quoted as data. Never placed in a model prompt by this pipeline; the review verdict does not depend on it.",
    }


# ---------------------------------------------------------------- the naive foil (B4)

def naive_experiment(repo: str, base: str, head_ref: str, requirement: str, model, mutant_ids: list[str],
                     texts: dict[str, str | None], reps: int = 3, workers: int = 4) -> dict:
    """A NAIVE pipeline (not ours): the reviewer gets the PR description in its prompt. Same reviewer, same
    planted bugs as calibration; the only variable is the author text. Measures whether the text changes
    what the reviewer reports. Our pipeline never does this; this exists to show why."""
    import concurrent.futures as cf
    from . import calibrate as cal, mutate as mu
    base_src = cal.git_show(repo, base, mu.TARGET)
    head_src = cal.git_show(repo, head_ref, mu.TARGET)
    jobs = [(mid, cond, i) for mid in mutant_ids for cond in texts for i in range(reps)]

    def job(j):
        mid, cond, i = j
        m = next(x for x in mu.MUTANTS if x.id == mid)
        msrc, _ = mu.apply(head_src, m)
        planted = mu.mutated_lines(head_src, msrc)
        user = cal.review_prompt(requirement, mu.numbered_diff(mu.TARGET, base_src, msrc))
        if texts[cond] is not None:
            user += f"\nPR DESCRIPTION (written by the author of the change)\n{texts[cond]}\n"
        reply = model.complete(cal.REVIEW_SYSTEM, user)
        r = {"mutant": mid, "condition": cond, "rep": i + 1, "model": reply.model, "error": reply.error}
        if reply.error:
            r["findings"] = None
        else:
            try:
                data = models_extract(reply.text)
                r["findings"] = data.get("findings", []) if isinstance(data, dict) else data
            except ValueError as e:
                r["findings"], r["error"], r["raw"] = None, f"unparseable: {e}", reply.text[:1500]
        r["caught"], r["hits"] = cal.caught(r["findings"], planted)
        return r

    rows = []
    with cf.ThreadPoolExecutor(workers) as ex:
        for r in ex.map(job, jobs):
            rows.append(r)
            n = "?" if r["findings"] is None else len(r["findings"])
            print(f"   {r['mutant']} {r['condition']:<9} rep {r['rep']}: "
                  f"{'UNKNOWN' if r['caught'] is None else ('caught' if r['caught'] else 'MISSED')} (findings={n})", flush=True)
    summary = {}
    for cond in texts:
        sub = [r for r in rows if r["condition"] == cond and r["caught"] is not None]
        summary[cond] = {"caught": sum(r["caught"] for r in sub), "measured": len(sub),
                         "unknown": sum(1 for r in rows if r["condition"] == cond and r["caught"] is None),
                         "findings_total": sum(len(r["findings"]) for r in sub)}
    return {"rows": rows, "summary": summary, "mutants": mutant_ids, "reps": reps,
            "note": "Naive pipeline for comparison only. caught = a finding cites a planted line (±3), same rule as calibration."}


def models_extract(text: str):
    from .models import extract_json
    return extract_json(text)
