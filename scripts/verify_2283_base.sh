#!/usr/bin/env bash
# Ledger for #2283: agent tests (GenericsFormatterTests, incl. pre-existing ones) + reviewer receipts, base vs head.
#   - If they PASS on base  -> they don't prove the PR changed anything (placebo tests).
#   - If they FAIL on base and PASS on the PR -> they are real evidence of a behavior change.
# Usage: scripts/verify_2283_base.sh [path-to-msgpack-clone]
# Logs + TRX results land in out/2283/verify/ (gitignored).
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/env.sh"
REPO="$(cd "${1:-$MSGPACK_REPO}" && pwd)"
OUT="$HERE/../out/2283/verify"
WT_ROOT="${WT_ROOT:-$(dirname "$REPO")/msgpack-wt}"
BASE="32258fdb"
WT_BASE="$WT_ROOT/2283-base-with-agent-tests"
WT_HEAD="$WT_ROOT/2283-head"
TESTS=(
  "tests/MessagePack.SourceGenerator.Tests/GenericsFormatterTests.cs"
)
PROJECTS=(
  "tests/MessagePack.SourceGenerator.Tests/MessagePack.SourceGenerator.Tests.csproj"
)
FILTER="FullyQualifiedName~GenericsFormatterTests|FullyQualifiedName~EtScopeDriftReceiptsTests"
# Reviewer-written catching tests (ours, not the agent's), injected into BOTH sides.
RECEIPTS_DIR="$HERE/../receipts/2283"
RECEIPTS_DEST="tests/MessagePack.SourceGenerator.Tests"

mkdir -p "$OUT" "$WT_ROOT"
OUT="$(cd "$OUT" && pwd)"
cd "$REPO"
BRANCH="upstream/ju26-issue-2283"
git rev-parse -q --verify "$BRANCH" >/dev/null || BRANCH="origin/ju26-issue-2283"

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

echo "== Injecting reviewer receipts from receipts/2283 into both worktrees =="
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

# Counterfactual: the PR head with ONLY the global diagnostic filter reverted (crash fix kept).
# Shows which diagnostics the filter itself removes. TRX goes to out/2283/counterfactual/ (not the ledger).
CF="$HERE/../out/2283/counterfactual"; mkdir -p "$CF"; CF="$(cd "$CF" && pwd)"
TC="$WT_HEAD/src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs"
cp "$TC" "$CF/TypeCollector.head.cs"
python - "$TC" <<'PY'
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8", newline="").read()
a = "this.reportDiagnostic = reportAnalyzerDiagnostic is null ? null : diagnostic => ReportIfLocatedInCompilation(reportAnalyzerDiagnostic, diagnostic);"
assert s.count(a) == 1, "filter line not found"
open(p, "w", encoding="utf-8", newline="").write(s.replace(a, "this.reportDiagnostic = reportAnalyzerDiagnostic; // ET counterfactual: global filter removed"))
PY
echo; echo "########## head-without-filter (counterfactual) ##########"
( cd "$WT_HEAD" && ET_EVIDENCE_DIR="$CF/evidence" dotnet test "${PROJECTS[0]}" --filter "$FILTER"     --logger "trx;LogFileName=$CF/head-nofilter.trx" > "$CF/head-nofilter.log" 2>&1 )
grep -E "^\s*(Passed|Failed) |Passed:|Failed:" "$CF/head-nofilter.log" | head -30
cp "$CF/TypeCollector.head.cs" "$TC"

echo
echo "Logs: $OUT"
echo "Worktrees left for inspection: $WT_BASE  $WT_HEAD"
