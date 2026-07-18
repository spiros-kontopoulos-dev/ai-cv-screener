"""Run a compact demonstration of candidate-profile validation.

Execute inside the backend container with:

    python -m app.scripts.validate_candidate_schema

The script shows both sides of the Pydantic boundary: valid structured data
becomes a typed ``CandidateProfile``, while contradictory data is rejected
before it can reach candidate generation or PDF rendering.
"""

from copy import deepcopy

from pydantic import ValidationError

from app.schemas import CandidateProfile


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


def main() -> None:
    """Run the valid and invalid schema demonstrations."""

    payload = build_example_payload()
    demonstrate_valid_profile(payload)
    demonstrate_rejected_profile(payload)


if __name__ == "__main__":
    main()
