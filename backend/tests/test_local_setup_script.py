"""Safety and parity checks for the cross-platform setup assistants."""

import os
from pathlib import Path
import subprocess


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = Path(
    os.environ.get("AI_CV_SCREENER_REPOSITORY_ROOT", BACKEND_ROOT.parent)
)


def _read_environment(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name] = value
    return values


def test_powershell_setup_script_creates_local_env_without_exposing_keys() -> None:
    script = (BACKEND_ROOT / "setup.ps1").read_text(encoding="utf-8")

    assert ".env.example" in script
    assert 'Read-Host -Prompt $Prompt -AsSecureString' in script
    assert "CV_GROUNDED_ANSWER_PROVIDER" in script
    assert "GEMINI_API_KEY" in script
    assert "OPENAI_API_KEY" in script
    assert "Clear-ProviderKeys" in script
    assert "docker compose up --build" in script
    assert "Write-Host $key" not in script


def test_bash_setup_script_matches_provider_and_secret_safety_contract() -> None:
    script = (BACKEND_ROOT / "setup.sh").read_text(encoding="utf-8")

    assert "#!/usr/bin/env bash" in script
    assert ".env.example" in script
    assert "read -r -s" in script
    assert "CV_GROUNDED_ANSWER_PROVIDER" in script
    assert "GEMINI_API_KEY" in script
    assert "OPENAI_API_KEY" in script
    assert "clear_provider_keys" in script
    assert "docker compose up --build" in script
    assert 'printf "%s\\n" "$key"' not in script


def test_bash_setup_supports_no_key_mode_and_preserves_other_settings(
    tmp_path: Path,
) -> None:
    (tmp_path / ".env.example").write_text(
        "APP_NAME=AI CV Screener API\n"
        "GEMINI_API_KEY=old-gemini\n"
        "GOOGLE_API_KEY=old-google\n"
        "OPENAI_API_KEY=old-openai\n"
        "CV_GROUNDED_ANSWER_PROVIDER=auto\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(BACKEND_ROOT / "setup.sh"), str(tmp_path)],
        input="3\n",
        text=True,
        capture_output=True,
        check=True,
    )

    values = _read_environment(tmp_path / ".env")
    assert values["APP_NAME"] == "AI CV Screener API"
    assert values["CV_GROUNDED_ANSWER_PROVIDER"] == "deterministic"
    assert values["GEMINI_API_KEY"] == ""
    assert values["GOOGLE_API_KEY"] == ""
    assert values["OPENAI_API_KEY"] == ""
    assert "deterministic no-key" in result.stdout


def test_bash_setup_does_not_echo_hosted_provider_secret(tmp_path: Path) -> None:
    secret = "test-gemini-secret"
    (tmp_path / ".env.example").write_text(
        "UNCHANGED=value\n"
        "GEMINI_API_KEY=\n"
        "GOOGLE_API_KEY=\n"
        "OPENAI_API_KEY=\n"
        "CV_GROUNDED_ANSWER_PROVIDER=auto\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(BACKEND_ROOT / "setup.sh"), str(tmp_path)],
        input=f"1\n  {secret}  \n",
        text=True,
        capture_output=True,
        check=True,
    )

    values = _read_environment(tmp_path / ".env")
    assert values["UNCHANGED"] == "value"
    assert values["CV_GROUNDED_ANSWER_PROVIDER"] == "gemini"
    assert values["GEMINI_API_KEY"] == secret
    assert values["GOOGLE_API_KEY"] == ""
    assert values["OPENAI_API_KEY"] == ""
    assert secret not in result.stdout
    assert secret not in result.stderr


def test_bash_setup_help_is_safe_and_complete() -> None:
    """Both Bash entry points explain usage without touching environment files."""

    repository_root = REPOSITORY_ROOT
    commands = (
        ["bash", str(repository_root / "setup.sh"), "--help"],
        ["bash", str(BACKEND_ROOT / "setup.sh"), "--help"],
    )

    for command in commands:
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=True,
        )
        assert "Usage:" in result.stdout
        assert "Valid command combinations:" in result.stdout
        assert "What the command changes:" in result.stdout
        assert "Example" in result.stdout


def test_powershell_setup_files_include_help_guides() -> None:
    """Windows wrappers expose explicit help plus PowerShell comment help."""

    repository_root = REPOSITORY_ROOT
    for path in (repository_root / "setup.ps1", BACKEND_ROOT / "setup.ps1"):
        script = path.read_text(encoding="utf-8")
        assert ".SYNOPSIS" in script
        assert ".PARAMETER Help" in script
        assert "[switch]$Help" in script
        assert "Valid command combinations:" in script
        assert "What the command changes:" in script


def test_root_bash_setup_rejects_unknown_arguments_without_writing() -> None:
    """The public Bash wrapper fails clearly instead of ignoring bad options."""

    repository_root = REPOSITORY_ROOT
    result = subprocess.run(
        ["bash", str(repository_root / "setup.sh"), "--unknown"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "unknown argument" in result.stderr
    assert "--help" in result.stderr
