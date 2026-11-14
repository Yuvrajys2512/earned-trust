"""The agent-written PRs under review and their requirements.

Requirement text here is a short paraphrase of the upstream issue; it is the only
"intent" the reviewer gets. PR/commit text is never stored here (it is untrusted).
"""
from __future__ import annotations

from dataclasses import dataclass, field

BASE = "32258fdb"
ISSUE_URL = "https://github.com/MessagePack-CSharp/MessagePack-CSharp/issues/{}"


@dataclass(frozen=True)
class Requirement:
    id: str
    title: str
    summary: str
    # For regressions: (last good ref, first bad ref) as reported by the issue author.
    regressed_between: tuple[str, str] | None = None

    @property
    def url(self) -> str:
        return ISSUE_URL.format(self.id.lstrip("#"))


@dataclass(frozen=True)
class PR:
    key: str
    branch: str
    requirement: Requirement
    base: str = BASE
    notes: list[str] = field(default_factory=list)


PRS: dict[str, PR] = {
    "2234": PR(
        key="2234",
        branch="ju26-issue-2234",
        requirement=Requirement(
            id="#2234",
            title="The analyzer does not work if SuppressSourceGeneration = true",
            summary="Analyzer diagnostics stopped being reported for types marked "
            "SuppressSourceGeneration = true. Worked in 3.1.0, broken in 3.1.1.",
            regressed_between=("v3.1.0", "v3.1.1"),
        ),
    ),
    "2283": PR(
        key="2283",
        branch="ju26-issue-2283",
        requirement=Requirement(
            id="#2283",
            title="IndexOutOfRangeException for closed generic value type from referenced assembly",
            summary="Generator (CS8785) and analyzer (AD0001) crash when a [MessagePackObject] "
            "member's type is a closed generic value type defined in a referenced assembly.",
        ),
    ),
    "2129": PR(
        key="2129",
        branch="ju26-issue-2129",
        requirement=Requirement(
            id="#2129",
            title="Generate a formatter for a type in a referenced assembly",
            summary="Allow the source generator to produce formatters for types declared "
            "in another assembly.",
        ),
    ),
    "2297": PR(
        key="2297",
        branch="ju26-issue-2297",
        requirement=Requirement(
            id="#2297",
            title="Add [ExcludeFromCodeCoverage] to generated code",
            summary="Generated formatters/resolvers should be excluded from code coverage.",
        ),
    ),
}
