#!/usr/bin/env bash
# Build-only check for #2129 (no tests run): does the PR's own test code compile on its head?
# Builds the test projects the PR touches, on the head commit, and records exit code, wall time
# and every compiler error code. Logs land in out/2129/build/ (gitignored).
# Usage: scripts/build_2129.sh [path-to-msgpack-clone]
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/env.sh"
REPO="$(cd "${1:-$MSGPACK_REPO}" && pwd)"
OUT="$HERE/../out/2129/build"
WT_ROOT="${WT_ROOT:-$(dirname "$REPO")/msgpack-wt}"
WT_HEAD="$WT_ROOT/2129-head"
PROJECTS=(
  "tests/MessagePack.SourceGenerator.ExecutionTests/MessagePack.SourceGenerator.ExecutionTests.csproj"
  "tests/MessagePack.SourceGenerator.Tests/MessagePack.SourceGenerator.Tests.csproj"
)
mkdir -p "$OUT" "$WT_ROOT"
OUT="$(cd "$OUT" && pwd)"
cd "$REPO"
BRANCH="origin/ju26-issue-2129"
HEAD_SHA="$(git rev-parse "$BRANCH")"
dotnet build-server shutdown >/dev/null 2>&1 || true
git worktree remove --force "$WT_HEAD" >/dev/null 2>&1 || true
rm -rf "$WT_HEAD"
git worktree add --detach "$WT_HEAD" "$HEAD_SHA" >/dev/null
cd "$WT_HEAD"
# Same override as verify_2234_base.sh (L-04): under the pinned SDK 8.0.402 the generator
# fails to load (warning CS9057), so generated partial formatters are missing and the
# ExecutionTests fail with CS0535 on ANY commit. That is our environment, not the PR (L-29).
if [ -z "${ET_KEEP_GLOBAL_JSON:-}" ]; then
  printf '{ "sdk": { "version": "9.0.100", "rollForward": "latestFeature" } }\n' > global.json
  echo "== global.json overridden in worktree -> SDK $(dotnet --version)"
fi
: > "$OUT/summary.tsv"
for p in "${PROJECTS[@]}"; do
  name="$(basename "$p" .csproj)"
  start=$(date +%s)
  dotnet build "$p" -c Debug -nologo -clp:NoSummary > "$OUT/$name.log" 2>&1
  code=$?
  end=$(date +%s)
  errs="$(grep -oE 'error [A-Z]+[0-9]+' "$OUT/$name.log" | sort | uniq -c | awk '{print $3"x"$1}' | tr '\n' ' ')"
  printf '%s\t%s\t%s\t%s\t%s\n' "$name" "$code" "$((end-start))" "$HEAD_SHA" "${errs:-none}" | tee -a "$OUT/summary.tsv"
done
