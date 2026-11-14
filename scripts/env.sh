#!/usr/bin/env bash
# Source me: puts a user-local .NET 8 SDK on PATH (Git Bash on Windows or Linux/macOS).
# Install the SDK without admin rights:
#   Windows (PowerShell): & ./dotnet-install.ps1 -Channel 8.0 -InstallDir "$env:LOCALAPPDATA\Microsoft\dotnet" -NoPath
#   Linux/macOS:          ./dotnet-install.sh --channel 8.0 --install-dir ~/.dotnet
if [ -n "${LOCALAPPDATA:-}" ] && command -v cygpath >/dev/null; then
  _root="$(cygpath -u "$LOCALAPPDATA")/Microsoft/dotnet"
else
  _root="$HOME/.dotnet"
fi
if [ -x "$_root/dotnet" ] || [ -x "$_root/dotnet.exe" ]; then
  export DOTNET_ROOT="$_root"
  export PATH="$DOTNET_ROOT:$PATH"
fi
export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1 DOTNET_MULTILEVEL_LOOKUP=0
# Where the challenge repo clone lives (scripts/setup.sh default).
export MSGPACK_REPO="${MSGPACK_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/msgpack}"
unset _root
