"""Public HTTP request and response contracts for the WP8 application API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.cv_answer_generation import GroundedAnswerOutcome, GroundedAnswerProviderName


class ApiSchema(BaseModel):
    """Shared strict API model behaviour."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ApiErrorDetail(ApiSchema):
    field: str
    message: str


class ApiErrorBody(ApiSchema):
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)
    details: list[ApiErrorDetail] = Field(default_factory=list)


class ApiErrorResponse(ApiSchema):
    error: ApiErrorBody


class HealthProviderStatus(ApiSchema):
    requested_mode: Literal["auto", "openai", "gemini", "deterministic"]
    active_provider: GroundedAnswerProviderName
    model: str = Field(min_length=1, max_length=150)
    ready: bool


class HealthIndexStatus(ApiSchema):
    available: bool
    record_count: int = Field(ge=0)
    document_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    complete_document_count: int = Field(ge=0)
    incomplete_document_count: int = Field(ge=0)


class HealthResponse(ApiSchema):
    status: Literal["ok", "degraded"]
    service: str
    environment: str
    provider: HealthProviderStatus
    index: HealthIndexStatus

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "status": "ok",
                "service": "AI CV Screener API",
                "environment": "development",
                "provider": {
                    "requested_mode": "auto",
                    "active_provider": "deterministic",
                    "model": "deterministic-template-v1",
                    "ready": True,
                },
                "index": {
                    "available": True,
                    "record_count": 184,
                    "document_count": 30,
                    "candidate_count": 30,
                    "complete_document_count": 30,
                    "incomplete_document_count": 0,
                },
            }
        },
    )


class CandidateListItem(ApiSchema):
    candidate_id: str = Field(pattern=r"^candidate_\d{3}$")
    name: str = Field(min_length=1, max_length=200)
    professional_title: str = Field(min_length=1, max_length=200)
    source_filename: str = Field(min_length=1, max_length=500)
    cv_available: bool
    photo_available: bool


class CandidateListResponse(ApiSchema):
    count: int = Field(ge=0)
    candidates: list[CandidateListItem]

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "count": 1,
                "candidates": [
                    {
                        "candidate_id": "candidate_001",
                        "name": "Eleni Markou",
                        "professional_title": "Senior Python Backend Engineer",
                        "source_filename": (
                            "eleni-markou-senior-python-backend-engineer-cv.pdf"
                        ),
                        "cv_available": True,
                        "photo_available": False,
                    }
                ],
            }
        },
    )


class ChatRequest(ApiSchema):
    question: str = Field(min_length=1, max_length=2000)
    candidate_limit: int = Field(default=5, ge=1, le=10)

    @field_validator("question", mode="before")
    @classmethod
    def normalize_question(cls, value: object) -> object:
        """Collapse whitespace so blank-only input fails normal validation."""

        if isinstance(value, str):
            return " ".join(value.split())
        return value

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "question": (
                    "Which candidates have experience with Python, FastAPI, "
                    "and PostgreSQL?"
                ),
                "candidate_limit": 5,
            }
        },
    )


class ChatCandidate(ApiSchema):
    candidate_id: str = Field(pattern=r"^candidate_\d{3}$")
    name: str = Field(min_length=1, max_length=200)
    professional_title: str = Field(min_length=1, max_length=200)
    rank: int = Field(ge=1)
    support_level: Literal["complete", "partial"]
    relevance_score: float = Field(ge=0.0, le=1.0)
    coverage_score: float = Field(ge=0.0, le=1.0)
    matched_requirements: list[str]
    assessment: str = Field(min_length=1, max_length=4000)
    citation_ids: list[str]


class ChatSource(ApiSchema):
    source_id: str = Field(min_length=1, max_length=150)
    candidate_id: str = Field(pattern=r"^candidate_\d{3}$")
    candidate_name: str = Field(min_length=1, max_length=200)
    filename: str = Field(min_length=1, max_length=500)
    page: int = Field(ge=1)
    page_label: str = Field(min_length=1, max_length=100)
    section: str = Field(min_length=1, max_length=200)
    chunk_id: str = Field(min_length=1, max_length=150)
    supports: list[str]
    text: str = Field(min_length=1, max_length=1200)
    cv_url: str = Field(min_length=1, max_length=500)


class ChatResponse(ApiSchema):
    question: str = Field(min_length=1, max_length=2000)
    outcome: GroundedAnswerOutcome
    answer: str = Field(min_length=1, max_length=12000)
    provider: GroundedAnswerProviderName
    model: str = Field(min_length=1, max_length=150)
    provider_called: bool
    provider_attempts: int = Field(ge=0, le=10)
    answer_citation_ids: list[str]
    candidates: list[ChatCandidate]
    sources: list[ChatSource]
    warnings: list[str]

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "question": "Which candidates know Python and FastAPI?",
                "outcome": "supported",
                "answer": "The indexed evidence identifies Eleni Markou.",
                "provider": "deterministic",
                "model": "deterministic-template-v1",
                "provider_called": False,
                "provider_attempts": 0,
                "answer_citation_ids": ["candidate_001-source-1"],
                "candidates": [
                    {
                        "candidate_id": "candidate_001",
                        "name": "Eleni Markou",
                        "professional_title": "Senior Python Backend Engineer",
                        "rank": 1,
                        "support_level": "complete",
                        "relevance_score": 0.91,
                        "coverage_score": 1.0,
                        "matched_requirements": ["python", "fastapi"],
                        "assessment": "Complete source-backed match.",
                        "citation_ids": ["candidate_001-source-1"],
                    }
                ],
                "sources": [
                    {
                        "source_id": "candidate_001-source-1",
                        "candidate_id": "candidate_001",
                        "candidate_name": "Eleni Markou",
                        "filename": (
                            "eleni-markou-senior-python-backend-engineer-cv.pdf"
                        ),
                        "page": 1,
                        "page_label": "1",
                        "section": "professional_summary",
                        "chunk_id": "chunk_candidate_001_1",
                        "supports": ["python", "fastapi"],
                        "text": "Source-backed CV evidence.",
                        "cv_url": "/api/candidates/candidate_001/cv",
                    }
                ],
                "warnings": [
                    "Answer wording was generated by the deterministic no-key fallback."
                ],
            }
        },
    )
