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

@pytest.fixture
def valid_candidate_001_payload(valid_candidate_payload: dict) -> dict:
    """Return a profile that satisfies the controlled candidate_001 slot."""

    valid_candidate_payload.update(
        {
            "full_name": "Eleni Markou",
            "professional_title": "Senior Python Backend Engineer",
            "contact": {
                "email": "eleni.markou@example.com",
                "phone": "+30 690 000 0001",
                "city": "Athens",
                "country": "Greece",
            },
            "skills": [
                {
                    "name": "Python",
                    "category": "programming_language",
                    "years_of_experience": 8,
                },
                {
                    "name": "FastAPI",
                    "category": "framework",
                    "years_of_experience": 5,
                },
                {
                    "name": "PostgreSQL",
                    "category": "database",
                    "years_of_experience": 7,
                },
                {
                    "name": "Docker",
                    "category": "devops",
                    "years_of_experience": 6,
                },
                {
                    "name": "AWS",
                    "category": "cloud",
                    "years_of_experience": 5,
                },
            ],
            "languages": [
                {"name": "Greek", "proficiency": "native"},
                {"name": "English", "proficiency": "fluent"},
            ],
        }
    )

    valid_candidate_payload["summary"] = (
        "Senior backend engineer with eight years of Python experience "
        "building FastAPI and PostgreSQL services deployed through Docker "
        "on AWS for international product teams."
    )
    valid_candidate_payload["work_experience"][0].update(
        {
            "highlights": [
                "Built Python FastAPI services backed by PostgreSQL and AWS."
            ],
            "technologies": [
                "Python",
                "FastAPI",
                "PostgreSQL",
                "Docker",
                "AWS",
            ],
            "managed_team_size": 5,
        }
    )
    valid_candidate_payload["work_experience"].append(
        {
            "job_title": "Backend Engineer",
            "company": "BluePeak Applications",
            "location": "Athens, Greece",
            "start_date": "2018-07",
            "end_date": "2021-03",
            "highlights": [
                "Developed Python services and PostgreSQL data workflows."
            ],
            "technologies": ["Python", "PostgreSQL", "Docker"],
            "managed_team_size": None,
        }
    )

    return valid_candidate_payload
