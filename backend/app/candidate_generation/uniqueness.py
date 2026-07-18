"""Lightweight duplicate checks across generated candidate profiles.

The assignment needs varied CVs, but WP3 does not need semantic embeddings or
an advanced plagiarism detector. Deterministic exact signatures catch the
high-risk repetitions cheaply and keep this preparation workflow explainable.
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
    """Return exact cross-candidate duplicates using stable signatures."""

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
    """Raise one focused error when exact duplicate evidence is found."""

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
