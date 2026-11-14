#!/usr/bin/env bash
# Clone your fork of the challenge repo next to this project and fetch all agent branches + tags.
# Usage: scripts/setup.sh <your-fork-url> [target-dir]
#   e.g. scripts/setup.sh https://github.com/<you>/junction26-messagepack-csharp ../msgpack
set -euo pipefail

FORK_URL="${1:?Pass your fork URL (fork te-industry-tech-office/junction26-messagepack-csharp first)}"
TARGET="${2:-../msgpack}"
UPSTREAM="https://github.com/te-industry-tech-office/junction26-messagepack-csharp"

if [ ! -d "$TARGET/.git" ]; then
  git clone "$FORK_URL" "$TARGET"
fi
cd "$TARGET"
git remote get-url upstream >/dev/null 2>&1 || git remote add upstream "$UPSTREAM"
git fetch upstream 'refs/heads/ju26-*:refs/remotes/upstream/ju26-*' --tags

echo
echo "== Agent branches (base should be 32258fdb for all) =="
for b in 2234 2283 2129 2297; do
  r="upstream/ju26-issue-$b"
  printf '%-22s head=%s base=%s  ' "$r" "$(git rev-parse --short "$r")" "$(git rev-parse --short "$r~1")"
  git diff --shortstat "$r~1" "$r"
done

echo
echo "== .NET =="
if command -v dotnet >/dev/null; then
  dotnet --list-sdks
  echo "global.json wants: $(grep -o '"version": *"[^"]*"' global.json)"
else
  echo "dotnet not found. Install .NET SDK 8.0.4xx: https://dotnet.microsoft.com/download/dotnet/8.0"
fi
