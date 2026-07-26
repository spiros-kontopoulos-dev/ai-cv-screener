"""Find clear duplicates across generated candidate profiles.

This small dataset does not need a second embedding system for duplicate
detection. Exact normalised signatures catch the highest-risk repetitions:
identical IDs, names, emails, summaries, and employer/title histories. The
checks run before a profile is saved and again during final dataset validation.
"""

from collections.abc import Sequence

from app.schemas import CandidateProfile


class CandidateUniquenessError(ValueError):
    """Raised when a candidate repeats an accepted profile identity or text."""

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems = tuple(problems)
        super().__init__("; ".join(self.problems))


def find_profile_uniqueness_problems(
    candidate: CandidateProfile,
    accepted_profiles: Sequence[CandidateProfile],
) -> list[str]:
    """Return every exact duplicate problem between one profile and the collection."""

    problems: list[str] = []

    for existing in accepted_profiles:
        if candidate.candidate_id == existing.candidate_id:
            problems.append(
                f"candidate_id duplicates {existing.candidate_id!r}."
            )

        if _normalize(candidate.full_name) == _normalize(existing.full_name):
            problems.append(
                f"full_name duplicates candidate {existing.candidate_id}."
            )

        if (
            candidate.contact.email.casefold()
            == existing.contact.email.casefold()
        ):
            problems.append(
                f"email duplicates candidate {existing.candidate_id}."
            )

        if _normalize(candidate.summary) == _normalize(existing.summary):
            problems.append(
                f"summary duplicates candidate {existing.candidate_id}."
            )

        if _work_history_signature(candidate) == _work_history_signature(
            existing
        ):
            problems.append(
                "employer and job-title history duplicates candidate "
                f"{existing.candidate_id}."
            )

    return problems


def validate_profile_uniqueness(
    candidate: CandidateProfile,
    accepted_profiles: Sequence[CandidateProfile],
) -> None:
    """Raise a single clear error when exact duplicate checks fail."""

    problems = find_profile_uniqueness_problems(
        candidate,
        accepted_profiles,
    )
    if problems:
        raise CandidateUniquenessError(problems)


def _work_history_signature(
    profile: CandidateProfile,
) -> tuple[tuple[str, str], ...]:
    """Build an ordered exact signature from company and job title pairs."""

    return tuple(
        (_normalize(role.company), _normalize(role.job_title))
        for role in profile.work_experience
    )


def _normalize(value: str) -> str:
    """Normalize whitespace and casing for deterministic text comparisons."""

    return " ".join(value.casefold().split())
