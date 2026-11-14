#!/usr/bin/env bash
# Attention budget for #2297: can a machine clear the 222 regenerated snapshot files?
#
#   1. Worktree at the PR head.
#   2. Reset every changed snapshot (tests/**/Resources/**) back to its BASE bytes,
#      so nothing the agent committed can leak into the result.
#   3. Build the generator tests with WRITE_EXPECTED (the repo's own switch, see
#      CSharpSourceGeneratorVerifier`1+Test.cs WriteTreeToDiskIfNecessary) and run them:
#      the head generator rewrites every snapshot from the head templates.
#   4. Compare each regenerated file with the PR's committed file (git blob ids).
#      Identical -> machine-verified, auto-clear. Different / missing -> human.
#
# Usage: scripts/regen_2297.sh [path-to-msgpack-clone]
# Output: out/2297/regen/{snapshots.txt,test.log,regen.json}
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/env.sh"
REPO="$(cd "${1:-$MSGPACK_REPO}" && pwd)"
OUT="$HERE/../out/2297/regen"
WT_ROOT="${WT_ROOT:-$(dirname "$REPO")/msgpack-wt}"
WT="$WT_ROOT/2297-regen"
BASE="32258fdb"
PROJ="tests/MessagePack.SourceGenerator.Tests/MessagePack.SourceGenerator.Tests.csproj"

mkdir -p "$OUT" "$WT_ROOT"
OUT="$(cd "$OUT" && pwd)"
cd "$REPO"
BRANCH="upstream/ju26-issue-2297"
git rev-parse -q --verify "$BRANCH" >/dev/null || BRANCH="origin/ju26-issue-2297"
HEAD_SHA="$(git rev-parse "$BRANCH")"

dotnet build-server shutdown >/dev/null 2>&1 || true
git worktree remove --force "$WT" >/dev/null 2>&1 || true
rm -rf "$WT"; git worktree prune
git worktree add --detach "$WT" "$HEAD_SHA" >/dev/null || { echo "FATAL: worktree add failed" >&2; exit 2; }

git diff --name-only "$BASE" "$HEAD_SHA" -- 'tests/*/Resources/*' > "$OUT/snapshots.txt"
N=$(wc -l < "$OUT/snapshots.txt")
echo "== $N snapshot files changed by the PR; resetting them to base $BASE"
( cd "$WT" && xargs -a "$OUT/snapshots.txt" -d '\n' git checkout "$BASE" -- )
( cd "$WT" && xargs -a "$OUT/snapshots.txt" -d '\n' git diff --quiet "$BASE" -- ) \
  && echo "   reset ok: worktree snapshots == base" || { echo "FATAL: reset to base failed" >&2; exit 3; }

# SDK 9 in the throwaway worktree only (L-04).
printf '{ "sdk": { "version": "9.0.100", "rollForward": "latestFeature" } }\n' > "$WT/global.json"
# Add WRITE_EXPECTED without clobbering the project's own DefineConstants.
cat > "$OUT/write_expected.targets" <<'EOF'
<Project>
  <PropertyGroup><DefineConstants>$(DefineConstants);WRITE_EXPECTED</DefineConstants></PropertyGroup>
</Project>
EOF

# Warm the reference-pack cache with ONE test first. 160 parallel tests racing to download
# Microsoft.NETCore.App.Ref into an empty %TEMP%\test-packages leave a nupkg without its
# nuspec, and every test then fails before it writes a snapshot (L-07).
echo "== Warming reference-assembly cache (single test)"
( cd "$WT" && dotnet test "$PROJ" --filter "FullyQualifiedName~CodeCoverageExclusionTests" > "$OUT/warmup.log" 2>&1 )
grep -E "Passed!|Failed!" "$OUT/warmup.log" | tail -1

echo "== Regenerating with the head generator (SDK $(cd "$WT" && dotnet --version))"
( cd "$WT" && dotnet test "$PROJ" -p:CustomAfterMicrosoftCommonTargets="$(cygpath -w "$OUT/write_expected.targets" 2>/dev/null || echo "$OUT/write_expected.targets")" \
    --logger "trx;LogFileName=$OUT/regen.trx" > "$OUT/test.log" 2>&1 )
echo "   dotnet test exit $? (failures expected: embedded resources are base bytes)"
grep -E "Passed!|Failed!|Total tests" "$OUT/test.log" | tail -3

# Compare: blob id of the regenerated file (same clean filters as git) vs the PR's blob.
echo "== Comparing regenerated files with the PR's committed files"
python - "$WT" "$HEAD_SHA" "$BASE" "$OUT" <<'PY'
import json, subprocess, sys
wt, head, base, out = sys.argv[1:]
def git(*a): return subprocess.run(["git", "-C", wt, *a], capture_output=True, text=True, check=True).stdout.strip()
paths = [p for p in open(f"{out}/snapshots.txt", encoding="utf-8").read().splitlines() if p]
rows = []
for p in paths:
    want, was = git("rev-parse", f"{head}:{p}"), git("rev-parse", f"{base}:{p}")
    try:
        got = git("hash-object", p)
    except subprocess.CalledProcessError:
        got = None
    verdict = "identical" if got == want else ("missing" if got is None else ("not-regenerated" if got == was else "different"))
    rows.append({"path": p, "verdict": verdict, "pr_blob": want, "regen_blob": got, "base_blob": was})
counts = {}
for r in rows: counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
res = {"head": head, "base": base, "method": "reset snapshots to base, rebuild tests with WRITE_EXPECTED, run, git hash-object vs PR blob",
       "counts": counts, "files": rows}
json.dump(res, open(f"{out}/regen.json", "w", encoding="utf-8"), indent=2)
print("   " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
for r in rows:
    if r["verdict"] != "identical": print("   ", r["verdict"], r["path"])
PY
echo "-> $OUT/regen.json   (worktree left at $WT)"
