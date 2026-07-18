"""Tests for persisted candidate-generation CLI behavior."""

from collections.abc import Sequence
from copy import deepcopy
from pathlib import Path

from pydantic import SecretStr

from app.candidate_generation import (
    CandidateProviderError,
    load_candidate_profiles,
    save_candidate_profiles,
)
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
    """Return queued profiles or errors without making an API request."""

    def __init__(
        self,
        outcomes: list[CandidateProfile | Exception],
    ) -> None:
        self._outcomes = list(outcomes)
        self.calls = 0
        self.feedback_received: list[tuple[str, ...]] = []

    def generate(
        self,
        slot,
        *,
        correction_feedback: Sequence[str] = (),
    ) -> CandidateProfile:
        self.calls += 1
        self.feedback_received.append(tuple(correction_feedback))
        outcome = self._outcomes.pop(0)

        if isinstance(outcome, Exception):
            raise outcome

        return outcome


def _test_settings(
    output_path: Path,
    *,
    with_api_key: bool = False,
) -> Settings:
    """Return isolated settings without reading the developer's .env."""

    return Settings(
        candidate_dataset_plan_path=PLAN_PATH,
        candidate_profiles_output_path=output_path,
        candidate_generation_model="test-model",
        candidate_generation_max_retries=2,
        openai_api_key=(
            SecretStr("test-key") if with_api_key else None
        ),
    )


def _existing_profile(
    valid_candidate_payload: dict,
) -> CandidateProfile:
    """Create an unrelated saved profile for resume and overwrite tests."""

    payload = deepcopy(valid_candidate_payload)
    payload.update(
        {
            "candidate_id": "candidate_099",
            "full_name": "Alex Morgan",
        }
    )
    payload["contact"]["email"] = "alex.morgan@example.com"
    return CandidateProfile.model_validate(payload)


def test_dry_run_previews_selected_candidates(
    capsys,
    tmp_path: Path,
) -> None:
    """Dry-run selection must remain network- and filesystem-write-free."""

    factory_called = False

    def unexpected_factory(settings):
        nonlocal factory_called
        factory_called = True
        raise AssertionError("Provider factory must not run in dry-run mode.")

    output_path = tmp_path / "candidate_profiles.json"
    status = run_cli(
        ["--count", "2", "--dry-run"],
        settings=_test_settings(output_path),
        provider_factory=unexpected_factory,
    )

    captured = capsys.readouterr()

    assert status == 0
    assert factory_called is False
    assert output_path.exists() is False
    assert "CANDIDATE GENERATION DRY RUN" in captured.out
    assert "candidate_001 | Eleni Markou" in captured.out
    assert "candidate_002 | Jonas Keller" in captured.out
    assert "Selected slots: 2" in captured.out
    assert "OpenAI requests made: 0" in captured.out
    assert captured.err == ""


def test_real_generation_requires_an_api_key(
    capsys,
    tmp_path: Path,
) -> None:
    """A missing key should fail before any provider request."""

    status = run_cli(
        ["--candidate-id", "candidate_001"],
        settings=_test_settings(tmp_path / "candidate_profiles.json"),
    )

    captured = capsys.readouterr()

    assert status == 2
    assert "OPENAI_API_KEY is required" in captured.err


def test_real_generation_persists_an_accepted_profile(
    capsys,
    tmp_path: Path,
    valid_candidate_001_payload: dict,
) -> None:
    """Accepted structured output should be saved immediately and reported."""

    profile = CandidateProfile.model_validate(valid_candidate_001_payload)
    provider = StubProvider([profile])
    output_path = tmp_path / "candidate_profiles.json"

    status = run_cli(
        ["--candidate-id", "candidate_001", "--print-json"],
        settings=_test_settings(output_path, with_api_key=True),
        provider_factory=lambda settings: provider,
    )

    captured = capsys.readouterr()
    persisted_profiles = load_candidate_profiles(output_path)

    assert status == 0
    assert provider.calls == 1
    assert [item.candidate_id for item in persisted_profiles] == [
        "candidate_001"
    ]
    assert "ACCEPTED after 1 attempt(s)" in captured.out
    assert '"candidate_id": "candidate_001"' in captured.out
    assert "Generated and saved: 1" in captured.out
    assert "Profiles in output: 1" in captured.out


def test_existing_output_requires_explicit_resume_or_overwrite(
    capsys,
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """A normal run must never silently replace accepted preparation data."""

    output_path = tmp_path / "candidate_profiles.json"
    save_candidate_profiles(
        output_path,
        [_existing_profile(valid_candidate_payload)],
    )

    status = run_cli(
        ["--candidate-id", "candidate_001"],
        settings=_test_settings(output_path, with_api_key=True),
    )

    captured = capsys.readouterr()

    assert status == 2
    assert "Use --resume" in captured.err
    assert "--overwrite" in captured.err


def test_resume_skips_an_already_persisted_candidate_without_api_key(
    capsys,
    tmp_path: Path,
    valid_candidate_001_payload: dict,
) -> None:
    """A completed resume selection should perform no provider work."""

    output_path = tmp_path / "candidate_profiles.json"
    profile = CandidateProfile.model_validate(valid_candidate_001_payload)
    save_candidate_profiles(output_path, [profile])
    factory_called = False

    def unexpected_factory(settings):
        nonlocal factory_called
        factory_called = True
        raise AssertionError("Provider must not run for skipped profiles.")

    status = run_cli(
        ["--candidate-id", "candidate_001", "--resume"],
        settings=_test_settings(output_path),
        provider_factory=unexpected_factory,
    )

    captured = capsys.readouterr()

    assert status == 0
    assert factory_called is False
    assert "Skipped existing: 1" in captured.out
    assert "Provider attempts: 0" in captured.out
    assert "Profiles in output: 1" in captured.out


def test_overwrite_replaces_the_existing_collection(
    capsys,
    tmp_path: Path,
    valid_candidate_payload: dict,
    valid_candidate_001_payload: dict,
) -> None:
    """Overwrite should reset old data before saving the new selection."""

    output_path = tmp_path / "candidate_profiles.json"
    save_candidate_profiles(
        output_path,
        [_existing_profile(valid_candidate_payload)],
    )
    generated_profile = CandidateProfile.model_validate(
        valid_candidate_001_payload
    )
    provider = StubProvider([generated_profile])

    status = run_cli(
        ["--candidate-id", "candidate_001", "--overwrite"],
        settings=_test_settings(output_path, with_api_key=True),
        provider_factory=lambda settings: provider,
    )

    captured = capsys.readouterr()
    persisted_profiles = load_candidate_profiles(output_path)

    assert status == 0
    assert [profile.candidate_id for profile in persisted_profiles] == [
        "candidate_001"
    ]
    assert "Generated and saved: 1" in captured.out


def test_successful_profiles_remain_saved_when_a_later_slot_fails(
    capsys,
    tmp_path: Path,
    valid_candidate_001_payload: dict,
) -> None:
    """Per-candidate checkpoints make interrupted generation resumable."""

    first_profile = CandidateProfile.model_validate(
        valid_candidate_001_payload
    )
    provider = StubProvider(
        [
            first_profile,
            CandidateProviderError(
                "Invalid request.",
                retryable=False,
            ),
        ]
    )
    output_path = tmp_path / "candidate_profiles.json"

    status = run_cli(
        ["--count", "2"],
        settings=_test_settings(output_path, with_api_key=True),
        provider_factory=lambda settings: provider,
    )

    captured = capsys.readouterr()
    persisted_profiles = load_candidate_profiles(output_path)

    assert status == 1
    assert [profile.candidate_id for profile in persisted_profiles] == [
        "candidate_001"
    ]
    assert "FAILED:" in captured.err
    assert "Generated and saved: 1" in captured.out
    assert "Failed: 1" in captured.out


def test_cli_reports_invalid_selection_without_traceback(
    capsys,
    tmp_path: Path,
) -> None:
    """Developer input errors should produce concise actionable output."""

    status = run_cli(
        ["--candidate-id", "candidate_999", "--dry-run"],
        settings=_test_settings(tmp_path / "candidate_profiles.json"),
    )

    captured = capsys.readouterr()

    assert status == 2
    assert "ERROR: Unknown candidate ID" in captured.err


def test_overwrite_with_missing_api_key_preserves_existing_profiles(
    capsys,
    tmp_path: Path,
    valid_candidate_payload: dict,
) -> None:
    """Provider configuration must succeed before destructive replacement."""

    output_path = tmp_path / "candidate_profiles.json"
    existing = _existing_profile(valid_candidate_payload)
    save_candidate_profiles(output_path, [existing])

    status = run_cli(
        ["--candidate-id", "candidate_001", "--overwrite"],
        settings=_test_settings(output_path),
    )

    captured = capsys.readouterr()
    persisted_profiles = load_candidate_profiles(output_path)

    assert status == 2
    assert "OPENAI_API_KEY is required" in captured.err
    assert [profile.candidate_id for profile in persisted_profiles] == [
        "candidate_099"
    ]
