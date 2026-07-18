"""Tests for bounded generation, compliance feedback, and retry behavior."""

from collections.abc import Sequence
from pathlib import Path

import pytest

from app.candidate_generation import (
    CandidateGenerationFailed,
    CandidateProviderError,
    generate_candidate_with_retries,
    load_candidate_dataset_plan,
)
from app.schemas import CandidateProfile


PLAN_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "dataset"
    / "candidate_dataset_plan.json"
)


class StubProvider:
    """Return predefined profiles or provider errors without network calls."""

    def __init__(self, outcomes: list[CandidateProfile | Exception]) -> None:
        self._outcomes = list(outcomes)
        self.feedback_received: list[tuple[str, ...]] = []

    def generate(
        self,
        slot,
        *,
        correction_feedback: Sequence[str] = (),
    ) -> CandidateProfile:
        self.feedback_received.append(tuple(correction_feedback))
        outcome = self._outcomes.pop(0)

        if isinstance(outcome, Exception):
            raise outcome

        return outcome


def _candidate_001_slot():
    return load_candidate_dataset_plan(PLAN_PATH).candidates[0]


def test_generation_accepts_a_matching_profile_on_first_attempt(
    valid_candidate_001_payload: dict,
) -> None:
    """A valid response should not spend the retry budget."""

    profile = CandidateProfile.model_validate(valid_candidate_001_payload)
    provider = StubProvider([profile])

    result = generate_candidate_with_retries(
        _candidate_001_slot(),
        provider=provider,
        max_retries=2,
    )

    assert result.profile == profile
    assert result.attempts == 1
    assert provider.feedback_received == [()]


def test_generation_retries_with_deterministic_correction_feedback(
    valid_candidate_001_payload: dict,
) -> None:
    """A slot mismatch should be explained to the next model attempt."""

    incorrect_payload = {
        **valid_candidate_001_payload,
        "contact": {
            **valid_candidate_001_payload["contact"],
            "city": "Patras",
        },
    }
    incorrect_profile = CandidateProfile.model_validate(incorrect_payload)
    corrected_profile = CandidateProfile.model_validate(
        valid_candidate_001_payload
    )
    provider = StubProvider([incorrect_profile, corrected_profile])

    result = generate_candidate_with_retries(
        _candidate_001_slot(),
        provider=provider,
        max_retries=2,
    )

    assert result.attempts == 2
    assert provider.feedback_received[0] == ()
    assert any(
        "city must be 'Athens'" in problem
        for problem in provider.feedback_received[1]
    )


def test_generation_retries_a_transient_provider_failure(
    valid_candidate_001_payload: dict,
) -> None:
    """Temporary API failures may use the same bounded retry budget."""

    profile = CandidateProfile.model_validate(valid_candidate_001_payload)
    provider = StubProvider(
        [
            CandidateProviderError("Temporary timeout.", retryable=True),
            profile,
        ]
    )

    result = generate_candidate_with_retries(
        _candidate_001_slot(),
        provider=provider,
        max_retries=2,
    )

    assert result.attempts == 2
    assert provider.feedback_received == [(), ()]


def test_generation_stops_immediately_on_non_retryable_provider_error() -> None:
    """Authentication and invalid-request errors should not waste API calls."""

    provider = StubProvider(
        [CandidateProviderError("Invalid API key.", retryable=False)]
    )

    with pytest.raises(CandidateGenerationFailed) as raised:
        generate_candidate_with_retries(
            _candidate_001_slot(),
            provider=provider,
            max_retries=2,
        )

    assert raised.value.attempts == 1
    assert raised.value.reasons == ("Invalid API key.",)


def test_generation_stops_after_the_fixed_attempt_budget(
    valid_candidate_001_payload: dict,
) -> None:
    """Two retries mean at most three total provider requests."""

    invalid_payload = {
        **valid_candidate_001_payload,
        "contact": {
            **valid_candidate_001_payload["contact"],
            "city": "Patras",
        },
    }
    invalid_profile = CandidateProfile.model_validate(invalid_payload)
    provider = StubProvider(
        [invalid_profile, invalid_profile, invalid_profile]
    )

    with pytest.raises(CandidateGenerationFailed) as raised:
        generate_candidate_with_retries(
            _candidate_001_slot(),
            provider=provider,
            max_retries=2,
        )

    assert raised.value.attempts == 3
    assert len(provider.feedback_received) == 3
