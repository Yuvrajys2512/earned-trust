#!/usr/bin/env bash
# Time Machine for #2234: replay the review factory on the commit that CAUSED the bug.
#
# The #2234 regression ("analyzer silent when SuppressSourceGeneration = true") was introduced by
# 1a74a620 (25 Dec 2024), merged in upstream PR #2106 with zero reviews (see `et timemachine`).
# The agent's tests for #2234 are placebos on the challenge base (they pass before its change).
# Here we aim the SAME tests at 1a74a620^ (parent) vs 1a74a620: if they pass on the parent and fail
# on 1a74a620, the factory would have caught the original regression at review time.
#
# Usage: scripts/timemachine_2234.sh [path-to-msgpack-clone]
# Output: out/2234/timemachine/{base,head}-MessagePack.SourceGenerator.Tests.trx + logs
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/env.sh"
REPO="$(cd "${1:-$MSGPACK_REPO}" && pwd)"
OUT="$HERE/../out/2234/timemachine"
WT_ROOT="${WT_ROOT:-$(dirname "$REPO")/msgpack-wt}"
BAD="1a74a620"
TEST="tests/MessagePack.SourceGenerator.Tests/SuppressSourceGenerationAnalyzerTests.cs"
PROJ="tests/MessagePack.SourceGenerator.Tests/MessagePack.SourceGenerator.Tests.csproj"
FILTER="FullyQualifiedName~SuppressSourceGenerationAnalyzerTests"

mkdir -p "$OUT" "$WT_ROOT"
OUT="$(cd "$OUT" && pwd)"
WOUT="$(cygpath -w "$OUT" 2>/dev/null || echo "$OUT")"
cd "$REPO"
BRANCH="upstream/ju26-issue-2234"
git rev-parse -q --verify "$BRANCH" >/dev/null || BRANCH="origin/ju26-issue-2234"

dotnet build-server shutdown >/dev/null 2>&1 || true
for spec in "base:$BAD^" "head:$BAD"; do
  side="${spec%%:*}"; rev="${spec#*:}"; wt="$WT_ROOT/tm-$side"
  git worktree remove --force "$wt" >/dev/null 2>&1 || true
  rm -rf "$wt"; git worktree prune
  git worktree add --detach "$wt" "$rev" >/dev/null || { echo "FATAL: worktree $rev" >&2; exit 2; }
  git show "$BRANCH:$TEST" > "$wt/$TEST"          # the agent's tests, unchanged
  printf '{ "sdk": { "version": "9.0.100", "rollForward": "latestFeature" } }\n' > "$wt/global.json"
  echo "== $side = $(git rev-parse --short=8 "$rev") + agent tests from $BRANCH"
  ( cd "$wt" && dotnet test "$PROJ" --filter "$FILTER" \
      --logger "trx;LogFileName=$WOUT\\$side-MessagePack.SourceGenerator.Tests.trx" > "$OUT/$side.log" 2>&1 )
  grep -E "^\s+(Passed|Failed) |Passed!|Failed!" "$OUT/$side.log"
done
echo "-> $OUT   (next: uv run et timemachine 2234)"
