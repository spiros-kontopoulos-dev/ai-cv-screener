"""Structured contracts for source-grounded recruiter answers.

The model-facing schema is deliberately smaller than the retrieval result. WP6
already decides which candidates and evidence are safe to expose. WP7 asks the
LLM only to explain that bounded result without inventing identities, changing
support status, or adding candidates that were not retrieved.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


GroundedAnswerOutcome = Literal["supported", "partial", "unsupported"]


class GroundedCandidateAnswer(BaseModel):
    """One candidate-specific explanation returned by the answer model."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    candidate_id: str = Field(min_length=1, max_length=100)
    candidate_name: str = Field(min_length=1, max_length=200)
    professional_title: str = Field(min_length=1, max_length=200)
    assessment: str = Field(min_length=1, max_length=4000)
    matched_requirements: list[str] = Field(min_length=1, max_length=50)

    @field_validator("matched_requirements")
    @classmethod
    def validate_unique_requirements(cls, values: list[str]) -> list[str]:
        """Reject duplicate or empty requirement labels in structured output."""

        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("Matched requirement labels cannot be empty.")
        if len(normalized) != len(set(normalized)):
            raise ValueError("Matched requirement labels must be unique.")
        return normalized


class GroundedAnswerDraft(BaseModel):
    """Structured draft generated strictly from the final WP6 context."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    outcome: GroundedAnswerOutcome
    answer: str = Field(min_length=1, max_length=12000)
    candidates: list[GroundedCandidateAnswer] = Field(max_length=30)
    limitations: list[str] = Field(max_length=30)

    @field_validator("limitations")
    @classmethod
    def validate_limitations(cls, values: list[str]) -> list[str]:
        """Normalize limitation messages and prevent repeated warnings."""

        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("Limitation messages cannot be empty.")
        if len(normalized) != len(set(normalized)):
            raise ValueError("Limitation messages must be unique.")
        return normalized
