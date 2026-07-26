#!/usr/bin/env bash

# Small Linux/macOS entry point for local setup.
# The real implementation lives in backend/setup.sh so it can be tested.

set -euo pipefail

show_help() {
    cat <<'HELP'
AI CV Screener local setup

Usage:
  bash ./setup.sh
  bash ./setup.sh --help
  ./setup.sh
  ./setup.sh --help

Valid command combinations:
  No arguments     Start the interactive provider configuration.
  -h, --help       Print this guide and exit without changing anything.

Interactive choices:
  1                Configure Gemini and save GEMINI_API_KEY locally.
  2                Configure OpenAI and save OPENAI_API_KEY locally.
  3                Configure deterministic no-key answer mode.

What the command changes:
  Creates .env from .env.example when .env does not exist.
  Updates only provider-related values in the existing .env file.
  Clears provider keys that are not used by the selected mode.
  Never prints the entered API key. The local .env file is ignored by Git.

Examples:
  bash ./setup.sh
  bash ./setup.sh --help
HELP
}

case "${1:-}" in
    -h|--help)
        if [[ $# -ne 1 ]]; then
            printf 'ERROR: --help cannot be combined with other arguments.\n' >&2
            exit 2
        fi
        show_help
        exit 0
        ;;
    "")
        ;;
    *)
        printf 'ERROR: unknown argument: %s\nRun bash ./setup.sh --help for usage.\n' "$1" >&2
        exit 2
        ;;
esac

if [[ $# -ne 0 ]]; then
    printf 'ERROR: setup accepts no positional arguments.\nRun bash ./setup.sh --help for usage.\n' >&2
    exit 2
fi

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
implementation_path="$project_root/backend/setup.sh"

if [[ ! -f "$implementation_path" ]]; then
    printf 'Setup implementation was not found at %s\n' "$implementation_path" >&2
    exit 1
fi

exec bash "$implementation_path" "$project_root"
