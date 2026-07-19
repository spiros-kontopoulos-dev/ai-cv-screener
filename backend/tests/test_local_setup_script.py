"""Static safety checks for the PowerShell local setup assistant."""

from pathlib import Path


def test_setup_script_creates_local_env_without_exposing_keys() -> None:
    # Docker mounts the backend directory at /app, so the test validates the
    # implementation stored inside backend/. The repository-root setup.ps1 is
    # intentionally only a stable user-facing wrapper around this script.
    script = (Path(__file__).resolve().parents[1] / "setup.ps1").read_text(
        encoding="utf-8"
    )

    assert ".env.example" in script
    assert 'Read-Host -Prompt $Prompt -AsSecureString' in script
    assert 'CV_GROUNDED_ANSWER_PROVIDER' in script
    assert 'GEMINI_API_KEY' in script
    assert 'OPENAI_API_KEY' in script
    assert 'docker compose up --build' in script
    assert 'Write-Host $key' not in script
