"""Tests for dry-run and real candidate-generation CLI behavior."""

from collections.abc import Sequence
from pathlib import Path

from pydantic import SecretStr

from app.candidate_generation import CandidateProviderError
from app.core.config import Settings
from app.schemas import CandidateProfile
from app.scripts.generate_candidate_profiles import run_cli


PLAN_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "dataset"
    / "candidate_dataset_plan.json"
)


class StubProvider:
    """Return one deterministic profile without making an API request."""

    def __init__(self, profile: CandidateProfile) -> None:
        self.profile = profile
        self.calls = 0

    def generate(
        self,
        slot,
        *,
        correction_feedback: Sequence[str] = (),
    ) -> CandidateProfile:
        self.calls += 1
        return self.profile


def _test_settings(*, with_api_key: bool = False) -> Settings:
    """Return isolated settings without reading the developer's .env."""

    return Settings(
        candidate_dataset_plan_path=PLAN_PATH,
        candidate_generation_model="test-model",
        candidate_generation_max_retries=2,
        openai_api_key=(
            SecretStr("test-key") if with_api_key else None
        ),
    )


def test_dry_run_previews_selected_candidates(capsys) -> None:
    """Dry-run selection must remain network-free after OpenAI is added."""

    factory_called = False

    def unexpected_factory(settings):
        nonlocal factory_called
        factory_called = True
        raise AssertionError("Provider factory must not run in dry-run mode.")

    status = run_cli(
        ["--count", "2", "--dry-run"],
        settings=_test_settings(),
        provider_factory=unexpected_factory,
    )

    captured = capsys.readouterr()

    assert status == 0
    assert factory_called is False
    assert "CANDIDATE GENERATION DRY RUN" in captured.out
    assert "candidate_001 | Eleni Markou" in captured.out
    assert "candidate_002 | Jonas Keller" in captured.out
    assert "Selected slots: 2" in captured.out
    assert "OpenAI requests made: 0" in captured.out
    assert captured.err == ""


def test_real_generation_requires_an_api_key(capsys) -> None:
    """A missing key should fail before any provider request."""

    status = run_cli(
        ["--candidate-id", "candidate_001"],
        settings=_test_settings(),
    )

    captured = capsys.readouterr()

    assert status == 2
    assert "OPENAI_API_KEY is required" in captured.err


def test_real_generation_prints_accepted_profile_and_summary(
    capsys,
    valid_candidate_001_payload: dict,
) -> None:
    """Patch 02 should validate and display a generated profile."""

    profile = CandidateProfile.model_validate(valid_candidate_001_payload)
    provider = StubProvider(profile)

    status = run_cli(
        ["--candidate-id", "candidate_001", "--print-json"],
        settings=_test_settings(with_api_key=True),
        provider_factory=lambda settings: provider,
    )

    captured = capsys.readouterr()

    assert status == 0
    assert provider.calls == 1
    assert "ACCEPTED after 1 attempt(s)" in captured.out
    assert '"candidate_id": "candidate_001"' in captured.out
    assert "Accepted: 1" in captured.out
    assert "Profiles persisted: 0" in captured.out


def test_real_generation_returns_failure_status(capsys) -> None:
    """A rejected candidate should produce a non-zero process status."""

    class FailingProvider:
        def generate(self, slot, *, correction_feedback=()):
            raise CandidateProviderError(
                "Invalid request.",
                retryable=False,
            )

    status = run_cli(
        ["--candidate-id", "candidate_001"],
        settings=_test_settings(with_api_key=True),
        provider_factory=lambda settings: FailingProvider(),
    )

    captured = capsys.readouterr()

    assert status == 1
    assert "FAILED:" in captured.err
    assert "Failed: 1" in captured.out


def test_cli_reports_invalid_selection_without_traceback(capsys) -> None:
    """Developer input errors should produce concise actionable output."""

    status = run_cli(
        ["--candidate-id", "candidate_999", "--dry-run"],
        settings=_test_settings(),
    )

    captured = capsys.readouterr()

    assert status == 2
    assert "ERROR: Unknown candidate ID" in captured.err
