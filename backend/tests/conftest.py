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


@pytest.fixture
def valid_candidate_002_payload() -> dict:
    """Return a profile that satisfies candidate_002 after normalization."""

    return {
        "candidate_id": "candidate_002",
        "full_name": "Jonas Keller",
        "professional_title": "Python Backend Engineer",
        "profession": "backend_engineering",
        "seniority": "mid",
        # This is intentionally provisional. Python derives 7.7 years from
        # the employment dates before the profile is accepted.
        "years_of_experience": 6,
        "summary": (
            "Experienced mid-level backend engineer building Python and Django "
            "services with PostgreSQL, Redis, and Docker for product teams."
        ),
        "contact": {
            "email": "jonas.keller@example.com",
            "phone": "+49 30 5550 0192",
            "city": "Berlin",
            "country": "Germany",
        },
        "work_experience": [
            {
                "job_title": "Python Backend Engineer",
                "company": "Rheinwerk Digital",
                "location": "Berlin, Germany",
                "start_date": "2018-12",
                "end_date": None,
                "highlights": [
                    "Built production Django APIs with PostgreSQL and Redis."
                ],
                "technologies": [
                    "Python",
                    "Django",
                    "PostgreSQL",
                    "Redis",
                    "Docker",
                ],
                "managed_team_size": None,
            }
        ],
        "education": [],
        "skills": [
            {
                "name": "Python",
                "category": "programming_language",
                "years_of_experience": 6,
            },
            {
                "name": "Django",
                "category": "framework",
                "years_of_experience": 5,
            },
            {
                "name": "PostgreSQL",
                "category": "database",
                "years_of_experience": 5,
            },
            {
                "name": "Redis",
                "category": "database",
                "years_of_experience": 4,
            },
            {
                "name": "Docker",
                "category": "devops",
                "years_of_experience": 4,
            },
        ],
        "languages": [
            {"name": "German", "proficiency": "native"},
            {"name": "English", "proficiency": "fluent"},
        ],
        "certifications": [
            {
                "name": "Python Web Engineering Certificate",
                "issuer": "European Software Guild",
                "year": 2024,
            }
        ],
        "projects": [],
    }

@pytest.fixture
def portrait_plan_factory(tmp_path):
    """Write a small valid portrait coverage plan for isolated CLI tests."""

    import json

    def write_plan(candidate_ids: list[str]):
        path = tmp_path / "candidate_portrait_plan.json"
        path.write_text(
            json.dumps(
                {
                    "plan_version": 1,
                    "portrait_count": len(candidate_ids),
                    "purpose": (
                        "Test portrait coverage plan for isolated candidate "
                        "rendering and generation workflows."
                    ),
                    "selection_strategy": (
                        "Use the exact candidate identifiers supplied by the "
                        "test while keeping the plan deterministic."
                    ),
                    "portrait_candidate_ids": sorted(candidate_ids),
                }
            ),
            encoding="utf-8",
        )
        return path

    return write_plan
