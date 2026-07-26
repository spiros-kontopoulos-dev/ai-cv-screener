#!/usr/bin/env bash

# Configure the local answer provider without printing or committing API keys.
# This script creates or updates the repository-root .env file.

set -euo pipefail

show_help() {
    cat <<'HELP'
AI CV Screener setup implementation

Usage:
  bash backend/setup.sh PROJECT_ROOT
  bash backend/setup.sh --help

Valid command combinations:
  PROJECT_ROOT      Run interactive setup for that repository root.
  -h, --help        Print this guide and exit without changing anything.

What the command changes:
  Reads PROJECT_ROOT/.env.example and creates or updates PROJECT_ROOT/.env.
  Stores only the selected provider mode and local provider key.
  Clears keys for providers that are not selected.
  Never prints the entered secret.

Examples:
  bash backend/setup.sh /home/user/projects/ai-cv-screener
  bash backend/setup.sh --help
HELP
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    if [[ $# -ne 1 ]]; then
        printf 'ERROR: --help cannot be combined with PROJECT_ROOT.\n' >&2
        exit 2
    fi
    show_help
    exit 0
fi

if [[ $# -ne 1 ]]; then
    printf 'ERROR: expected exactly one PROJECT_ROOT argument.\n' >&2
    printf 'Run bash backend/setup.sh --help for usage.\n' >&2
    exit 2
fi

project_root=$1
example_path="$project_root/.env.example"
environment_path="$project_root/.env"

# Replace one NAME=value line in .env, or add it when it is missing.
set_environment_value() {
    local name=$1
    local value=$2
    local temp_path
    local found=0

    temp_path=$(mktemp "${environment_path}.tmp.XXXXXX")

    while IFS= read -r line || [[ -n "$line" ]]; do
        case "$line" in
            "$name="*)
                printf '%s=%s\n' "$name" "$value" >> "$temp_path"
                found=1
                ;;
            *)
                printf '%s\n' "$line" >> "$temp_path"
                ;;
        esac
    done < "$environment_path"

    if [[ $found -eq 0 ]]; then
        printf '%s=%s\n' "$name" "$value" >> "$temp_path"
    fi

    mv "$temp_path" "$environment_path"
}

trim_value() {
    # Remove spaces accidentally copied before or after an API key without
    # printing the key or putting it in a command-line argument.
    printf '%s' "$1" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'
}

# Read a provider key without showing the typed characters.
read_secret_value() {
    local prompt=$1
    local secret

    IFS= read -r -s -p "$prompt: " secret
    printf '\n' >&2
    trim_value "$secret"
}

# Keep only the selected provider key. This prevents an old key from changing
# provider selection later.
clear_provider_keys() {
    set_environment_value "GEMINI_API_KEY" ""
    set_environment_value "GOOGLE_API_KEY" ""
    set_environment_value "OPENAI_API_KEY" ""
}

if [[ ! -f "$example_path" ]]; then
    printf '.env.example was not found at %s\n' "$example_path" >&2
    exit 1
fi

if [[ ! -f "$environment_path" ]]; then
    cp "$example_path" "$environment_path"
    printf 'Created .env from .env.example.\n'
else
    printf 'Updating the existing local .env file.\n'
fi

printf '\nChoose grounded-answer mode:\n'
printf '  1. Gemini (free-tier option; requires a Google AI Studio key)\n'
printf '  2. OpenAI (requires an OpenAI API key and available credits)\n'
printf '  3. Deterministic no-key mode\n'

IFS= read -r -p 'Enter 1, 2, or 3: ' choice

case "$choice" in
    1)
        key=$(read_secret_value 'Paste the Gemini API key')
        if [[ -z "$key" ]]; then
            printf 'A Gemini API key is required for option 1.\n' >&2
            exit 1
        fi
        clear_provider_keys
        set_environment_value "CV_GROUNDED_ANSWER_PROVIDER" "gemini"
        set_environment_value "GEMINI_API_KEY" "$key"
        mode='Gemini'
        ;;
    2)
        key=$(read_secret_value 'Paste the OpenAI API key')
        if [[ -z "$key" ]]; then
            printf 'An OpenAI API key is required for option 2.\n' >&2
            exit 1
        fi
        clear_provider_keys
        set_environment_value "CV_GROUNDED_ANSWER_PROVIDER" "openai"
        set_environment_value "OPENAI_API_KEY" "$key"
        mode='OpenAI'
        ;;
    3)
        clear_provider_keys
        set_environment_value "CV_GROUNDED_ANSWER_PROVIDER" "deterministic"
        mode='deterministic no-key'
        ;;
    *)
        printf 'Invalid selection. Run ./setup.sh again and choose 1, 2, or 3.\n' >&2
        exit 1
        ;;
esac

printf '\nLocal configuration saved for %s mode.\n' "$mode"
printf 'The .env file is ignored by Git and must never be committed.\n\n'
printf 'Next command:\n'
printf '  docker compose up --build\n'
