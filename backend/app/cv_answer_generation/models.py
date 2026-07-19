"""Structured contracts for grounded recruiter answers and source references.

WP6 already decides which candidates and evidence are safe to expose. WP7 asks
an optional LLM only to explain that bounded result. Candidate identity,
requirement coverage, and source provenance remain deterministic application
contracts rather than facts the model may change.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


GroundedAnswerOutcome = Literal["supported", "partial", "unsupported"]
GroundedAnswerProviderName = Literal["openai", "gemini", "deterministic"]


class GroundedCandidateAnswer(BaseModel):
    """One candidate-specific explanation returned by the answer layer."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    candidate_id: str = Field(min_length=1, max_length=100)
    candidate_name: str = Field(min_length=1, max_length=200)
    professional_title: str = Field(min_length=1, max_length=200)
    assessment: str = Field(min_length=1, max_length=4000)
    matched_requirements: list[str] = Field(min_length=1, max_length=50)
    citation_ids: list[str] = Field(min_length=1, max_length=30)

    @field_validator("matched_requirements", "citation_ids")
    @classmethod
    def validate_unique_non_empty_values(cls, values: list[str]) -> list[str]:
        """Reject duplicate or empty requirement and citation identifiers."""

        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("List values cannot be empty.")
        if len(normalized) != len(set(normalized)):
            raise ValueError("List values must be unique.")
        return normalized


class GroundedAnswerDraft(BaseModel):
    """Structured draft generated strictly from the final WP6 context."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    outcome: GroundedAnswerOutcome
    answer: str = Field(min_length=1, max_length=12000)
    answer_citation_ids: list[str] = Field(max_length=100)
    candidates: list[GroundedCandidateAnswer] = Field(max_length=30)
    limitations: list[str] = Field(max_length=30)

    @field_validator("answer_citation_ids", "limitations")
    @classmethod
    def validate_unique_non_empty_values(cls, values: list[str]) -> list[str]:
        """Normalize source IDs and warnings while preventing duplicates."""

        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("List values cannot be empty.")
        if len(normalized) != len(set(normalized)):
            raise ValueError("List values must be unique.")
        return normalized


class GroundedAnswerSource(BaseModel):
    """One validated source exposed by the final answer response."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_id: str = Field(min_length=1, max_length=150)
    candidate_id: str = Field(min_length=1, max_length=100)
    candidate_name: str = Field(min_length=1, max_length=200)
    source_filename: str = Field(min_length=1, max_length=500)
    page_label: str = Field(min_length=1, max_length=100)
    section_name: str = Field(min_length=1, max_length=200)
    chunk_id: str = Field(min_length=1, max_length=150)
    supports: list[str] = Field(max_length=50)
    evidence_excerpt: str = Field(min_length=1, max_length=1200)


class GroundedAnswerResponse(BaseModel):
    """Final API-ready answer contract with validated sources and warnings."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    outcome: GroundedAnswerOutcome
    provider: GroundedAnswerProviderName
    model: str = Field(min_length=1, max_length=150)
    provider_called: bool
    provider_attempts: int = Field(ge=0, le=10)
    answer: str = Field(min_length=1, max_length=12000)
    answer_citation_ids: list[str] = Field(max_length=100)
    candidates: list[GroundedCandidateAnswer] = Field(max_length=30)
    sources: list[GroundedAnswerSource] = Field(max_length=100)
    warnings: list[str] = Field(max_length=50)
