"""Calibrate stage, part 1: plant known bugs ("mutants") in the PR's changed regions.

Like Threat Image Projection at airport security: we hide known threats among real
bags and measure the screener's catch rate. Two screeners are measured per mutant:
  * the TEST SUITE (agent's tests + reviewer receipts): does any test go red?
  * the AI REVIEWER: shown the PR diff with the bug woven in (never told a bug was
    planted), does it report a finding at the planted line?

Mutants are hand-written operators over the PR's changed hunks (±10 lines). They
model realistic slips for this code: last-wins instead of first-wins, break vs
continue, dropped diagnostics, inverted guards, and the same edit made in only one
of the two duplicated code paths (properties vs fields).
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass

TARGET = "src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs"
# The changed code exists twice in GetObjectInfo: occurrence 0 = property loop, 1 = field loop.
REGION = {0: "properties", 1: "fields"}
ANCHORS = {
    0: "foreach (IPropertySymbol item in instanceMembers.OfType<IPropertySymbol>())",
    1: "foreach (IFieldSymbol item in formattedType.GetAllMembers().OfType<IFieldSymbol>())",
}


@dataclass(frozen=True)
class Mutant:
    id: str
    region: int          # occurrence index of `old` in the file (0 = properties, 1 = fields)
    kind: str
    description: str     # what bug this models (never shown to the reviewer)
    old: str
    new: str


INT_GUARD = """                        if (!intMembers.ContainsKey(member.IntKey))
                        {
                            intMembers.Add(member.IntKey, (member, item.Type));
                        }"""
STR_GUARD = """                        if (!stringMembers.ContainsKey(member.StringKey))
                        {
                            stringMembers.Add(member.StringKey, (member, item.Type));
                        }"""
CONTINUE = "                            continue; // The key kind does not match the other members; the diagnostic is reported, so skip this member."
MIXED_COND = "if ((isIntKey && intKey == null) || (!isIntKey && stringKey == null))"
DUP_INT_DIAG = """                        if (intMembers.ContainsKey(intKey!.Value))
                        {
                            this.reportDiagnostic?.Invoke(Diagnostic.Create(MsgPack00xMessagePackAnalyzer.KeysMustBeUnique, item.DeclaringSyntaxReferences.FirstOrDefault()?.GetSyntax().GetLocation()));
                        }"""

MUTANTS: list[Mutant] = [
    Mutant("M01", 0, "semantics", "duplicate int key: last member wins instead of first (properties)",
           INT_GUARD, "                        intMembers[member.IntKey] = (member, item.Type);"),
    Mutant("M02", 0, "semantics", "duplicate string key: last member wins instead of first (properties)",
           STR_GUARD, "                        stringMembers[member.StringKey] = (member, item.Type);"),
    Mutant("M03", 0, "control-flow", "mismatched key kind: `continue` removed, so the crash on mixed keys returns (properties)",
           CONTINUE + "\n", ""),
    Mutant("M04", 0, "control-flow", "mismatched key kind: `break` instead of `continue` drops every later member (properties)",
           CONTINUE, CONTINUE.replace("continue;", "break;   ")),
    Mutant("M05", 0, "inverted-guard", "guard inverted: int members are only added when the key already exists, so none are serialized (properties)",
           "if (!intMembers.ContainsKey(member.IntKey))", "if (intMembers.ContainsKey(member.IntKey))"),
    Mutant("M06", 0, "lost-diagnostic", "MsgPack005 for duplicate int keys no longer reported; member is dropped with no error (properties)",
           DUP_INT_DIAG + "\n\n", ""),
    Mutant("M07", 0, "condition", "mixed-key check flipped (`!= null`): every int member after the first is reported and skipped (properties)",
           MIXED_COND, "if ((isIntKey && intKey != null) || (!isIntKey && stringKey == null))"),
    Mutant("M08", 1, "semantics", "duplicate int key: last member wins instead of first (fields)",
           INT_GUARD, "                        intMembers[member.IntKey] = (member, item.Type);"),
    Mutant("M09", 1, "control-flow", "mismatched key kind: `break` instead of `continue` drops every later member (fields)",
           CONTINUE, CONTINUE.replace("continue;", "break;   ")),
    Mutant("M10", 1, "inverted-guard", "guard inverted: string members are only added when the key already exists (fields)",
           "if (!stringMembers.ContainsKey(member.StringKey))", "if (stringMembers.ContainsKey(member.StringKey))"),
]


def apply(src: str, m: Mutant) -> tuple[str, int]:
    """Return (mutated source, 1-based line of the first changed line)."""
    anchor = src.find(ANCHORS[m.region])
    if anchor == -1:
        raise ValueError(f"{m.id}: region anchor not found")
    start = src.find(m.old, anchor)
    end_of_region = src.find(ANCHORS[m.region + 1], anchor) if m.region + 1 in ANCHORS else -1
    if start == -1 or (end_of_region != -1 and start > end_of_region):
        raise ValueError(f"{m.id}: snippet not found in region {REGION[m.region]}")
    line = src.count("\n", 0, start) + 1
    return src[:start] + m.new + src[start + len(m.old):], line


def mutated_lines(head_src: str, mutant_src: str) -> list[int]:
    """1-based line numbers in the *mutant* file that differ from the head file (for catch matching)."""
    out = []
    sm = difflib.SequenceMatcher(a=head_src.splitlines(), b=mutant_src.splitlines(), autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        # A deletion has no line of its own in the new file. A reviewer describing it will cite
        # a line somewhere around the gap, so the span widens by the size of the deleted block
        # (rule fixed in L-08 and applied to every deletion mutant alike).
        widen = (i2 - i1) if tag == "delete" else 0
        out.extend(range(max(1, j1 + 1 - widen), max(j2, j1 + 1) + widen + 1))
    return sorted(set(out))


def numbered_diff(path: str, base_src: str, head_src: str, context: int = 6) -> str:
    """Unified diff with new-file line numbers on every line, so reviewer findings can cite lines exactly."""
    a, b = base_src.splitlines(), head_src.splitlines()
    out = [f"--- a/{path}", f"+++ b/{path}"]
    for group in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_grouped_opcodes(context):
        i1, j1 = group[0][1], group[0][3]
        out.append(f"@@ base line {i1 + 1}, new line {j1 + 1} @@")
        for tag, a1, a2, b1, b2 in group:
            if tag == "equal":
                out += [f"{b1 + k + 1:>5}   {b[b1 + k]}" for k in range(b2 - b1)]
            if tag in ("delete", "replace"):
                out += [f"{'':>5} - {a[k]}" for k in range(a1, a2)]
            if tag in ("insert", "replace"):
                out += [f"{k + 1:>5} + {b[k]}" for k in range(b1, b2)]
    return "\n".join(out)
