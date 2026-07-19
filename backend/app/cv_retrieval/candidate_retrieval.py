"""Candidate-aware orchestration over assisted chunk retrieval."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.cv_retrieval.assisted_retrieval import (
    AssistedCvRetriever,
    CvAssistedRetrievalError,
    build_assisted_cv_retriever,
)
from app.cv_retrieval.candidate_ranking import (
    CandidateCvRetrievalResult,
    rank_candidates,
)
from app.cv_retrieval.models import (
    CvRawRetrievalContractError,
    RawCvRetrievalQuery,
)


class CvCandidateRetrievalError(RuntimeError):
    """Raised when candidate-level retrieval cannot be completed."""


@dataclass(frozen=True, slots=True)
class CandidateRetrievalConfig:
    """Resolve candidate and per-candidate evidence limits safely."""

    default_candidate_limit: int = 10
    max_candidate_limit: int = 30
    default_evidence_limit: int = 4
    max_evidence_limit: int = 8

    def __post_init__(self) -> None:
        if self.default_candidate_limit < 1 or self.max_candidate_limit < 1:
            raise ValueError("Candidate retrieval limits must be positive.")
        if self.default_candidate_limit > self.max_candidate_limit:
            raise ValueError("Default candidate limit cannot exceed its maximum.")
        if self.default_evidence_limit < 1 or self.max_evidence_limit < 1:
            raise ValueError("Candidate evidence limits must be positive.")
        if self.default_evidence_limit > self.max_evidence_limit:
            raise ValueError("Default evidence limit cannot exceed its maximum.")

    def resolve_candidate_limit(self, requested: int | None) -> int:
        value = self.default_candidate_limit if requested is None else requested
        if value < 1 or value > self.max_candidate_limit:
            raise ValueError(
                "Candidate result limit must be between 1 and "
                f"{self.max_candidate_limit}."
            )
        return value

    def resolve_evidence_limit(self, requested: int | None) -> int:
        value = self.default_evidence_limit if requested is None else requested
        if value < 1 or value > self.max_evidence_limit:
            raise ValueError(
                "Evidence-per-candidate limit must be between 1 and "
                f"{self.max_evidence_limit}."
            )
        return value


@dataclass(frozen=True, slots=True)
class CandidateCvRetrievalQuery:
    """One recruiter question plus candidate-level output controls."""

    text: str
    candidate_limit: int | None = None
    semantic_result_limit: int | None = None
    evidence_limit: int | None = None

    def __post_init__(self) -> None:
        normalized = " ".join(self.text.split())
        if not normalized:
            raise CvRawRetrievalContractError(
                "Candidate retrieval question cannot be empty."
            )
        for field_name in (
            "candidate_limit",
            "semantic_result_limit",
            "evidence_limit",
        ):
            value = getattr(self, field_name)
            if value is not None and value < 1:
                raise CvRawRetrievalContractError(
                    f"{field_name.replace('_', ' ').title()} must be positive."
                )
        object.__setattr__(self, "text", normalized)


class CandidateAwareCvRetriever:
    """Group assisted evidence and rank one balanced result per candidate."""

    def __init__(
        self,
        config: CandidateRetrievalConfig,
        *,
        assisted_retriever: AssistedCvRetriever,
    ) -> None:
        self._config = config
        self._assisted_retriever = assisted_retriever

    def retrieve(
        self,
        query: CandidateCvRetrievalQuery,
    ) -> CandidateCvRetrievalResult:
        try:
            candidate_limit = self._config.resolve_candidate_limit(
                query.candidate_limit
            )
            evidence_limit = self._config.resolve_evidence_limit(
                query.evidence_limit
            )
            assisted_result = self._assisted_retriever.retrieve(
                RawCvRetrievalQuery(
                    text=query.text,
                    result_limit=query.semantic_result_limit,
                )
            )
            return rank_candidates(
                assisted_result,
                candidate_limit=candidate_limit,
                evidence_limit=evidence_limit,
            )
        except (
            CvAssistedRetrievalError,
            CvRawRetrievalContractError,
            ValueError,
        ) as error:
            raise CvCandidateRetrievalError(str(error)) from error


def build_candidate_aware_cv_retriever(
    settings: Settings,
) -> CandidateAwareCvRetriever:
    """Build candidate grouping over the configured assisted retriever."""

    return CandidateAwareCvRetriever(
        CandidateRetrievalConfig(
            default_candidate_limit=(
                settings.cv_candidate_retrieval_default_limit
            ),
            max_candidate_limit=settings.cv_candidate_retrieval_max_limit,
            default_evidence_limit=(
                settings.cv_candidate_retrieval_evidence_limit
            ),
            max_evidence_limit=(
                settings.cv_candidate_retrieval_max_evidence_limit
            ),
        ),
        assisted_retriever=build_assisted_cv_retriever(settings),
    )
