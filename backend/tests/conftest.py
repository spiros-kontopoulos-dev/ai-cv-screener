"""Reusable Pytest fixtures for candidate-schema tests."""

import pytest


@pytest.fixture
def valid_candidate_payload() -> dict:
    """Return one complete candidate payload known to pass validation.

    Pytest fixtures use function scope by default, so every test receives
    a fresh dictionary and can modify it without affecting another test.
    """

    return {
        "candidate_id": "candidate_001",
        "full_name": "Alex Morgan",
        "professional_title": "Senior Python Backend Engineer",
        "profession": "backend_engineering",
        "seniority": "senior",
        "years_of_experience": 8,
        "summary": (
            "Senior backend engineer experienced in building reliable "
            "Python APIs, data-processing services, PostgreSQL systems, "
            "and cloud applications for international product teams."
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
                # None represents an ongoing role.
                "end_date": None,
                "highlights": [
                    "Built FastAPI services used by international customers."
                ],
                "technologies": [
                    "Python",
                    "FastAPI",
                    "PostgreSQL",
                ],
                "managed_team_size": 4,
            }
        ],
        "education": [
            {
                "degree": "BSc",
                "field_of_study": "Computer Science",
                "institution": "Westbridge Technical University",
                "location": "Athens, Greece",
                "start_year": 2010,
                "end_year": 2014,
            }
        ],
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
            {
                "name": "Greek",
                "proficiency": "native",
            },
            {
                "name": "English",
                "proficiency": "fluent",
            },
        ],
        "certifications": [],
        "projects": [],
    }