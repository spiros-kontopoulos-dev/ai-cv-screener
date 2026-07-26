"""Small command-line demonstration of the candidate Pydantic boundary.

It validates one correct fictional payload and then shows that an obvious
seniority contradiction is rejected before data can be saved or rendered.
"""

import argparse
from collections.abc import Sequence
from copy import deepcopy
import sys

from app.scripts.cli_help import build_cli_parser

from pydantic import ValidationError

from app.schemas import CandidateProfile


def build_parser() -> argparse.ArgumentParser:
    """Describe the fixed valid/invalid schema demonstration."""

    return build_cli_parser(
        description=(
            "Run one valid candidate payload and one deliberately invalid "
            "payload through the CandidateProfile schema."
        ),
        sections=(
            (
                "Valid command combinations",
                (
                    "This demonstration uses fixed in-memory examples and takes no arguments.",
                    "Use --help to display this reference.",
                ),
            ),
            (
                "What the command changes",
                ("It validates in-memory data only. It writes nothing and makes no provider call.",),
            ),
            (
                "Example",
                ("python -m app.scripts.validate_candidate_schema",),
            ),
        ),
    )


def build_example_payload() -> dict:
    """Return a small fictional candidate payload for the demonstration."""

    return {
        "candidate_id": "candidate_001",
        "full_name": "Alex Morgan",
        "professional_title": "Senior Python Backend Engineer",
        "profession": "backend_engineering",
        "seniority": "senior",
        "years_of_experience": 8,
        "summary": (
            "Senior backend engineer experienced in reliable Python APIs, "
            "PostgreSQL services, Docker-based delivery, and technical "
            "leadership for international product teams."
        ),
        "contact": {
            "email": "alex.morgan@example.com",
            "phone": "+30 690 000 0000",
            "city": "Athens",
            "country": "Greece",
        },
        "work_experience": [
            {
                "job_title": "Senior Backend Engineer",
                "company": "Northstar Systems",
                "location": "Athens, Greece",
                "start_date": "2021-04",
                "end_date": None,
                "highlights": [
                    "Built FastAPI services used by international customers."
                ],
                "technologies": ["Python", "FastAPI", "PostgreSQL"],
                "managed_team_size": 4,
            }
        ],
        "education": [],
        "skills": [
            {
                "name": "Python",
                "category": "programming_language",
                "years_of_experience": 8,
            },
            {
                "name": "FastAPI",
                "category": "framework",
                "years_of_experience": 4,
            },
            {
                "name": "PostgreSQL",
                "category": "database",
                "years_of_experience": 7,
            },
        ],
        "languages": [
            {"name": "Greek", "proficiency": "native"},
            {"name": "English", "proficiency": "fluent"},
        ],
        "certifications": [],
        "projects": [],
    }


def demonstrate_valid_profile(payload: dict) -> None:
    """Validate and print a few fields from a correct candidate payload."""

    candidate = CandidateProfile.model_validate(payload)

    print("VALID PROFILE")
    print(f"  ID: {candidate.candidate_id}")
    print(f"  Name: {candidate.full_name}")
    print(f"  First skill: {candidate.skills[0].name}")


def demonstrate_rejected_profile(payload: dict) -> None:
    """Show that an obvious seniority contradiction is rejected."""

    invalid_payload = deepcopy(payload)
    invalid_payload["years_of_experience"] = 2

    try:
        CandidateProfile.model_validate(invalid_payload)
    except ValidationError as error:
        print("\nREJECTED PROFILE")
        print(f"  {error.errors()[0]['msg']}")
    else:
        raise RuntimeError("The intentionally invalid payload was not rejected.")


def run_cli(argv: Sequence[str] | None = None) -> int:
    """Parse help, then run the valid and invalid schema demonstrations."""

    build_parser().parse_args(tuple(argv or ()))
    payload = build_example_payload()
    demonstrate_valid_profile(payload)
    demonstrate_rejected_profile(payload)
    return 0


def main() -> None:
    """Execute the demonstration and expose its status to the shell."""

    raise SystemExit(run_cli(sys.argv[1:]))


if __name__ == "__main__":
    main()
