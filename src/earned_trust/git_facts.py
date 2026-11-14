"""Git facts: executed, reproducible evidence about a PR (no LLM involved).

Every fact carries the command that produced it, so the review record can show
*how* we know, not just *what* we claim.
"""
from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import PurePosixPath


class GitError(RuntimeError):
    pass


def git(repo: str, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, encoding="utf-8"
    )
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


def resolve_branch(repo: str, branch: str) -> str:
    for remote in ("upstream", "origin"):
        ref = f"{remote}/{branch}"
        if subprocess.run(
            ["git", "-C", repo, "rev-parse", "-q", "--verify", ref], capture_output=True
        ).returncode == 0:
            return ref
    raise GitError(f"branch {branch} not found under upstream/ or origin/ in {repo}")


# --- file classification -----------------------------------------------------

FILE_CLASSES = ("generated", "template", "template-output", "test", "doc", "src", "build")


def classify(path: str, tt_files: set[str]) -> str:
    """Classify a changed file. Heuristic, path-based; the class decides how it is cleared."""
    p = PurePosixPath(path)
    name = p.name.lower()
    in_snapshot_dir = path.startswith("tests/") and "/Resources/" in path
    if name.endswith(".g.cs") or (in_snapshot_dir and name.endswith(".cs")):
        return "generated"  # snapshot output; clearable by regenerate + byte-compare
    if p.suffix == ".tt":
        return "template"
    if p.suffix == ".cs" and str(p.with_suffix(".tt")) in tt_files:
        return "template-output"  # T4 output; clearable by re-running the template
    if p.suffix in {".md", ".txt"} or path.startswith("doc/"):
        return "doc"
    if path.startswith("tests/"):
        return "test"
    if p.suffix in {".csproj", ".props", ".targets", ".json", ".yml", ".yaml", ".sln"}:
        return "build"
    return "src"


@dataclass
class ChangedFile:
    path: str
    status: str
    added: int
    deleted: int
    cls: str


def changed_files(repo: str, base: str, head: str) -> list[ChangedFile]:
    status = {}
    for line in git(repo, "diff", "--name-status", "--no-renames", base, head).splitlines():
        st, path = line.split("\t", 1)
        status[path] = st
    tt_files = set(git(repo, "ls-tree", "-r", "--name-only", head).splitlines())
    tt_files = {f for f in tt_files if f.endswith(".tt")}
    out = []
    for line in git(repo, "diff", "--numstat", "--no-renames", base, head).splitlines():
        a, d, path = line.split("\t", 2)
        out.append(
            ChangedFile(
                path=path,
                status=status.get(path, "?"),
                added=int(a) if a != "-" else 0,
                deleted=int(d) if d != "-" else 0,
                cls=classify(path, tt_files),
            )
        )
    return out


# --- regression archaeology --------------------------------------------------


def is_ancestor(repo: str, maybe_ancestor: str, of: str) -> bool:
    return subprocess.run(
        ["git", "-C", repo, "merge-base", "--is-ancestor", maybe_ancestor, of],
        capture_output=True,
    ).returncode == 0


@dataclass
class Fact:
    claim: str
    holds: bool
    command: str
    detail: str = ""


@dataclass
class RegressionCheck:
    good: str
    bad: str
    facts: list[Fact] = field(default_factory=list)
    suspect_commits: list[str] = field(default_factory=list)
    verdict: str = ""


def regression_check(repo: str, base: str, good: str, bad: str, touched: list[str]) -> RegressionCheck:
    """Is the regression the issue reports even present in the code the agent worked on?

    The issue says `good` worked and `bad` broke. If `bad` (and the commits between)
    are not ancestors of `base`, the reported cause cannot be in this history, and a
    "fix" on this base is fixing something else.
    """
    rc = RegressionCheck(good=good, bad=bad)
    for ref in (good, bad):
        anc = is_ancestor(repo, ref, base)
        rc.facts.append(
            Fact(
                claim=f"{ref} is an ancestor of base {base}",
                holds=anc,
                command=f"git merge-base --is-ancestor {ref} {base}",
            )
        )
    if touched:
        log = git(repo, "log", "--format=%h %s", f"{good}..{bad}", "--", *touched).splitlines()
        rc.suspect_commits = log
        for line in log:
            sha = line.split(" ", 1)[0]
            anc = is_ancestor(repo, sha, base)
            rc.facts.append(
                Fact(
                    claim=f"suspect commit {line!r} is an ancestor of base",
                    holds=anc,
                    command=f"git merge-base --is-ancestor {sha} {base}",
                )
            )
    bad_in_history = rc.facts[1].holds
    suspects_in_history = [f for f in rc.facts[2:] if f.holds]
    if not bad_in_history and not suspects_in_history:
        rc.verdict = (
            f"NOT-IN-HISTORY: the reported regression ({good} -> {bad}) and every commit between "
            f"them that touches the PR's files are absent from base {base}. The PR cannot be fixing "
            "the reported cause; whatever it changes is something else."
        )
    elif not bad_in_history:
        rc.verdict = f"PARTIAL: {bad} not in history but {len(suspects_in_history)} suspect commit(s) are."
    else:
        rc.verdict = f"IN-HISTORY: {bad} is an ancestor of base; the regression may be present."
    return rc


def to_dict(obj) -> dict:
    return asdict(obj)
