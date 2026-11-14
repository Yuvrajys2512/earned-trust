#!/usr/bin/env bash
# Ledger for #2297: agent tests + reviewer receipts, base vs head.
#   - If they PASS on base  -> they don't prove the PR changed anything (placebo tests).
#   - If they FAIL on base and PASS on the PR -> they are real evidence of a behavior change.
# Usage: scripts/verify_2297_base.sh [path-to-msgpack-clone]
# Logs + TRX results land in out/2297/verify/ (gitignored).
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/env.sh"
REPO="$(cd "${1:-$MSGPACK_REPO}" && pwd)"
OUT="$HERE/../out/2297/verify"
WT_ROOT="${WT_ROOT:-$(dirname "$REPO")/msgpack-wt}"
BASE="32258fdb"
WT_BASE="$WT_ROOT/2297-base-with-agent-tests"
WT_HEAD="$WT_ROOT/2297-head"
TESTS=(
  "tests/MessagePack.SourceGenerator.Tests/CodeCoverageExclusionTests.cs"
)
PROJECTS=(
  "tests/MessagePack.SourceGenerator.Tests/MessagePack.SourceGenerator.Tests.csproj"
)
FILTER="FullyQualifiedName~CodeCoverageExclusionTests|FullyQualifiedName~EtCoverageReceiptsTests"
# Reviewer-written catching tests (ours, not the agent's), injected into BOTH sides.
RECEIPTS_DIR="$HERE/../receipts/2297"
RECEIPTS_DEST="tests/MessagePack.SourceGenerator.Tests"

mkdir -p "$OUT" "$WT_ROOT"
OUT="$(cd "$OUT" && pwd)"
cd "$REPO"
BRANCH="upstream/ju26-issue-2297"
git rev-parse -q --verify "$BRANCH" >/dev/null || BRANCH="origin/ju26-issue-2297"

fresh_worktree() {  # idempotent: remove an old worktree at the same path first
  # On Windows, MSBuild/dotnet build-server nodes hold file locks, so `worktree remove`
  # can unregister the tree but leave files behind; `worktree add` then fails (L-05).
  dotnet build-server shutdown >/dev/null 2>&1 || true
  git worktree remove --force "$1" >/dev/null 2>&1 || true
  rm -rf "$1"
  git worktree prune
  git worktree add --detach "$1" "$2" >/dev/null || { echo "FATAL: worktree add $1 failed" >&2; exit 2; }
}

echo "== Worktree: base $BASE + only the agent's new test files =="
fresh_worktree "$WT_BASE" "$BASE"
( cd "$WT_BASE" && git checkout "$BRANCH" -- "${TESTS[@]}" )

echo "== Worktree: PR head ($(git rev-parse --short "$BRANCH")) =="
fresh_worktree "$WT_HEAD" "$BRANCH"

echo "== Injecting reviewer receipts from receipts/2297 into both worktrees =="
for wt in "$WT_BASE" "$WT_HEAD"; do
  cp "$RECEIPTS_DIR"/*.cs "$wt/$RECEIPTS_DEST/"
done

# The repo pins SDK 8.0.402 (Roslyn 4.11) but compiles its generator against Roslyn 4.12,
# so under the pinned SDK the generator silently fails to load (warning CS9057) and the
# ExecutionTests don't compile. Use a 9.0 SDK in our throwaway worktrees only.
# See docs/LESSONS_LOG.md L-04. Set ET_KEEP_GLOBAL_JSON=1 to disable.
if [ -z "${ET_KEEP_GLOBAL_JSON:-}" ]; then
  for wt in "$WT_BASE" "$WT_HEAD"; do
    printf '{ "sdk": { "version": "9.0.100", "rollForward": "latestFeature" } }\n' > "$wt/global.json"
  done
  echo "== global.json overridden in worktrees -> SDK $(cd "$WT_HEAD" && dotnet --version)"
fi

run() {
  local dir="$1" label="$2"
  echo
  echo "########## $label ##########"
  for proj in "${PROJECTS[@]}"; do
    local name; name="$(basename "$proj" .csproj)"
    ( cd "$dir" && ET_EVIDENCE_DIR="$OUT/evidence/$label" dotnet test "$proj" --filter "$FILTER" \
        --logger "trx;LogFileName=$OUT/$label-$name.trx" \
        --logger "console;verbosity=normal" > "$OUT/$label-$name.log" 2>&1 )
    echo "-- $name (exit $?)"
    grep -E "^\s*(Passed|Failed|Skipped) |Total tests|Passed:|Failed:|error " "$OUT/$label-$name.log" | head -60
  done
}

run "$WT_BASE" "base"
run "$WT_HEAD" "head"

echo
echo "Logs: $OUT"
echo "Worktrees left for inspection: $WT_BASE  $WT_HEAD"
echo "Log the outcome in docs/LESSONS_LOG.md (L-01) and docs/FAILURE_MODES.md (F-06)."
