#!/bin/sh
set -eu

# Resolve the launcher itself, including symlinks and paths containing spaces.
UE_TRUE_SCRIPT_NAME=$(readlink -f -- "$0")
UE_PROJECT_ROOT=$(dirname -- "$UE_TRUE_SCRIPT_NAME")
UE_BINARY="$UE_PROJECT_ROOT/UeSim/Binaries/Linux/UeSim"

if [ ! -f "$UE_BINARY" ]; then
    printf 'MATRiX: runtime binary is missing: %s\n' "$UE_BINARY" >&2
    exit 1
fi
if [ ! -x "$UE_BINARY" ]; then
    chmod u+x "$UE_BINARY"
fi

cd "$UE_PROJECT_ROOT"
exec "$UE_BINARY" UeSim "$@"
