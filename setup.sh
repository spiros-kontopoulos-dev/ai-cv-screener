#!/usr/bin/env bash

# Small Linux/macOS entry point for local setup.
# The real implementation lives in backend/setup.sh so it can be tested.

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
implementation_path="$project_root/backend/setup.sh"

if [[ ! -f "$implementation_path" ]]; then
    printf 'Setup implementation was not found at %s\n' "$implementation_path" >&2
    exit 1
fi

exec bash "$implementation_path" "$project_root"
