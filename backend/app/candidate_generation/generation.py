"""Bounded generation orchestration for one controlled candidate slot."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.schemas import CandidateProfile

from .client import CandidateProviderError
from .compliance import validate_profile_against_slot
from .models import CandidateGenerationSlot


class CandidateProfileProvider(Protocol):
    """Small provider contract used by the orchestrator and deterministic tests."""

    def generate(
        self,
        slot: CandidateGenerationSlot,
        *,
        correction_feedback: Sequence[str] = (),
    ) -> CandidateProfile:
        """Generate one schema-valid profile for the supplied slot."""

        ...


@dataclass(frozen=True, slots=True)
class CandidateGenerationResult:
    """Successful candidate generation and the attempts it required."""

    profile: CandidateProfile
    attempts: int


class CandidateGenerationFailed(RuntimeError):
    """Raised after a non-retryable error or an exhausted retry budget."""

    def __init__(
        self,
        *,
        candidate_id: str,
        attempts: int,
        reasons: Sequence[str],
    ) -> None:
        self.candidate_id = candidate_id
        self.attempts = attempts
        self.reasons = tuple(reasons)

        formatted_reasons = "; ".join(self.reasons)
        super().__init__(
            f"{candidate_id} failed after {attempts} attempt(s): "
            f"{formatted_reasons}"
        )


def generate_candidate_with_retries(
    slot: CandidateGenerationSlot,
    *,
    provider: CandidateProfileProvider,
    max_retries: int,
) -> CandidateGenerationResult:
    """Generate, validate, and retry one candidate within a fixed budget.

    ``max_retries`` counts attempts *after* the first request. A value of two
    therefore allows at most three provider calls.
    """

    correction_feedback: tuple[str, ...] = ()
    total_attempts = max_retries + 1

    for attempt_number in range(1, total_attempts + 1):
        try:
            profile = provider.generate(
                slot,
                correction_feedback=correction_feedback,
            )
        except CandidateProviderError as error:
            if not error.retryable or attempt_number == total_attempts:
                raise CandidateGenerationFailed(
                    candidate_id=slot.candidate_id,
                    attempts=attempt_number,
                    reasons=[str(error)],
                ) from error

            # Provider failures such as a timeout do not indicate a problem in
            # the candidate content, so the next attempt reuses the base prompt.
            correction_feedback = ()
            continue

        compliance_problems = validate_profile_against_slot(profile, slot)
        if not compliance_problems:
            return CandidateGenerationResult(
                profile=profile,
                attempts=attempt_number,
            )

        if attempt_number == total_attempts:
            raise CandidateGenerationFailed(
                candidate_id=slot.candidate_id,
                attempts=attempt_number,
                reasons=compliance_problems,
            )

        correction_feedback = tuple(compliance_problems)

    # The loop always returns or raises. This guard protects future refactors
    # and keeps static type checkers aware that no implicit None is possible.
    raise RuntimeError("Candidate generation ended without a result.")
