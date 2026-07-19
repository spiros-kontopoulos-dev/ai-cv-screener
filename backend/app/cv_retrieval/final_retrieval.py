"""Final supported-candidate selection and prompt-ready CV evidence budgets.

Candidate-aware retrieval deliberately keeps partial and zero-coverage rows so
engineers can inspect ranking behavior. A downstream answer generator must not
receive that entire diagnostic pool. This module establishes the final WP6
quality boundary:

* fully supported candidates are preferred over partial matches;
* partial candidates are used only when no complete match exists;
* unsupported questions return no candidate evidence;
* candidate, chunk, and character budgets are enforced deterministically;
* every prompt-ready evidence block preserves PDF provenance.

No LLM is called here. The output is a bounded, source-traceable context package
that a later work package may pass to an answer-generation layer.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal

from app.core.config import Settings
from app.cv_retrieval.candidate_ranking import (
    CandidateEvidenceSelection,
    CandidateCvRetrievalResult,
    RankedCvCandidate,
)
from app.cv_retrieval.candidate_retrieval import (
    CandidateAwareCvRetriever,
    CandidateCvRetrievalQuery,
    CvCandidateRetrievalError,
    build_candidate_aware_cv_retriever,
)
from app.cv_retrieval.models import (
    CvRawRetrievalContractError,
    RawCvRetrievalSource,
)


FinalSupportLevel = Literal["complete", "partial"]
FinalRetrievalOutcome = Literal["supported", "partial", "unsupported"]


class CvFinalRetrievalError(RuntimeError):
    """Raised when final evidence selection or budgeting cannot complete."""


@dataclass(frozen=True, slots=True)
class FinalRetrievalConfig:
    """Thresholds and hard budgets for final recruiter-question evidence."""

    default_candidate_limit: int = 5
    max_candidate_limit: int = 10
    candidate_pool_limit: int = 15
    candidate_evidence_pool_limit: int = 4
    evidence_per_candidate_limit: int = 3
    max_total_evidence_chunks: int = 12
    max_context_characters: int = 7000
    max_evidence_text_characters: int = 900
    complete_min_candidate_score: float = 0.45
    partial_min_candidate_score: float = 0.30
    partial_min_coverage: float = 0.65

    def __post_init__(self) -> None:
        integer_fields = {
            "default_candidate_limit": self.default_candidate_limit,
            "max_candidate_limit": self.max_candidate_limit,
            "candidate_pool_limit": self.candidate_pool_limit,
            "candidate_evidence_pool_limit": self.candidate_evidence_pool_limit,
            "evidence_per_candidate_limit": self.evidence_per_candidate_limit,
            "max_total_evidence_chunks": self.max_total_evidence_chunks,
            "max_context_characters": self.max_context_characters,
            "max_evidence_text_characters": self.max_evidence_text_characters,
        }
        for field_name, value in integer_fields.items():
            if value < 1:
                raise ValueError(
                    f"Final retrieval setting {field_name} must be positive."
                )
        if self.default_candidate_limit > self.max_candidate_limit:
            raise ValueError(
                "Default final candidate limit cannot exceed its maximum."
            )
        if self.candidate_pool_limit < self.max_candidate_limit:
            raise ValueError(
                "Candidate pool limit must cover the maximum final limit."
            )
        if (
            self.evidence_per_candidate_limit
            > self.candidate_evidence_pool_limit
        ):
            raise ValueError(
                "Final evidence limit cannot exceed the candidate evidence pool."
            )
        for field_name in (
            "complete_min_candidate_score",
            "partial_min_candidate_score",
            "partial_min_coverage",
        ):
            value = getattr(self, field_name)
            if not math.isfinite(value) or value < 0.0 or value > 1.0:
                raise ValueError(
                    f"Final retrieval threshold {field_name} must be between "
                    "zero and one."
                )
        if self.partial_min_candidate_score > self.complete_min_candidate_score:
            raise ValueError(
                "Partial score threshold cannot exceed the complete threshold."
            )

    def resolve_candidate_limit(self, requested: int | None) -> int:
        value = self.default_candidate_limit if requested is None else requested
        if value < 1 or value > self.max_candidate_limit:
            raise ValueError(
                "Final candidate limit must be between 1 and "
                f"{self.max_candidate_limit}."
            )
        return value


@dataclass(frozen=True, slots=True)
class FinalCvRetrievalQuery:
    """One recruiter question plus final-output controls."""

    text: str
    candidate_limit: int | None = None
    semantic_result_limit: int | None = None

    def __post_init__(self) -> None:
        normalized = " ".join(self.text.split())
        if not normalized:
            raise CvRawRetrievalContractError(
                "Final retrieval question cannot be empty."
            )
        for field_name in ("candidate_limit", "semantic_result_limit"):
            value = getattr(self, field_name)
            if value is not None and value < 1:
                raise CvRawRetrievalContractError(
                    f"{field_name.replace('_', ' ').title()} must be positive."
                )
        object.__setattr__(self, "text", normalized)


@dataclass(frozen=True, slots=True)
class FinalCvEvidence:
    """One budgeted prompt-ready evidence block and its source provenance."""

    order: int
    chunk_id: str
    text: str
    source: RawCvRetrievalSource
    condition_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.order < 1 or not self.chunk_id.strip() or not self.text.strip():
            raise ValueError("Final evidence requires order, chunk ID, and text.")
        if len(self.condition_keys) != len(set(self.condition_keys)):
            raise ValueError("Final evidence condition keys must be unique.")

    @property
    def source_label(self) -> str:
        return (
            f"{self.source.source_filename} | page {self.source.page_label} | "
            f"{self.source.section_name} | {self.chunk_id}"
        )


@dataclass(frozen=True, slots=True)
class FinalCvCandidate:
    """One final candidate safe to expose to answer generation."""

    rank: int
    original_candidate_rank: int
    support_level: FinalSupportLevel
    candidate_id: str
    candidate_name: str | None
    professional_title: str | None
    candidate_score: float
    coverage_score: float
    condition_quality_score: float
    semantic_support_score: float
    matched_condition_labels: tuple[str, ...]
    total_condition_count: int
    evidence: tuple[FinalCvEvidence, ...]

    def __post_init__(self) -> None:
        if self.rank < 1 or self.original_candidate_rank < 1:
            raise ValueError("Final candidate ranks must be positive.")
        if not self.candidate_id.strip() or not self.evidence:
            raise ValueError("Final candidates require identity and evidence.")
        if self.support_level not in {"complete", "partial"}:
            raise ValueError("Unsupported final candidate support level.")
        for field_name in (
            "candidate_score",
            "coverage_score",
            "condition_quality_score",
            "semantic_support_score",
        ):
            value = getattr(self, field_name)
            if not math.isfinite(value) or value < 0.0 or value > 1.0:
                raise ValueError(f"{field_name} must be between zero and one.")
        if len(self.matched_condition_labels) > self.total_condition_count:
            raise ValueError("Matched conditions cannot exceed total conditions.")
        if tuple(item.order for item in self.evidence) != tuple(
            range(1, len(self.evidence) + 1)
        ):
            raise ValueError("Final evidence order must be consecutive.")
        if any(
            evidence.source.candidate_id != self.candidate_id
            for evidence in self.evidence
        ):
            raise ValueError("Final evidence cannot cross candidate IDs.")


@dataclass(frozen=True, slots=True)
class FinalCvRetrievalResult:
    """Final bounded evidence output before any answer-generation model."""

    query: FinalCvRetrievalQuery
    candidate_result: CandidateCvRetrievalResult
    outcome: FinalRetrievalOutcome
    support_message: str
    requested_candidate_limit: int
    max_total_evidence_chunks: int
    max_context_characters: int
    candidates: tuple[FinalCvCandidate, ...]
    context_text: str
    budget_exhausted: bool

    def __post_init__(self) -> None:
        if self.outcome not in {"supported", "partial", "unsupported"}:
            raise ValueError("Unsupported final retrieval outcome.")
        if not self.support_message.strip():
            raise ValueError("Final retrieval support message is required.")
        if self.requested_candidate_limit < 1:
            raise ValueError("Requested final candidate limit must be positive.")
        if len(self.candidates) > self.requested_candidate_limit:
            raise ValueError("Final result exceeded the candidate limit.")
        if self.evidence_chunk_count > self.max_total_evidence_chunks:
            raise ValueError("Final result exceeded the evidence-chunk budget.")
        if len(self.context_text) > self.max_context_characters:
            raise ValueError("Final context exceeded its character budget.")
        if tuple(candidate.rank for candidate in self.candidates) != tuple(
            range(1, len(self.candidates) + 1)
        ):
            raise ValueError("Final candidate ranks must be consecutive.")
        if self.outcome == "unsupported" and self.candidates:
            raise ValueError("Unsupported results cannot expose candidates.")
        if self.outcome != "unsupported" and not self.candidates:
            raise ValueError("Supported results must expose candidate evidence.")

    @property
    def returned_candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def evidence_chunk_count(self) -> int:
        return sum(len(candidate.evidence) for candidate in self.candidates)

    @property
    def context_character_count(self) -> int:
        return len(self.context_text)


class FinalCvRetriever:
    """Apply support thresholds and hard budgets to candidate-aware results."""

    def __init__(
        self,
        config: FinalRetrievalConfig,
        *,
        candidate_retriever: CandidateAwareCvRetriever,
    ) -> None:
        self._config = config
        self._candidate_retriever = candidate_retriever

    def retrieve(self, query: FinalCvRetrievalQuery) -> FinalCvRetrievalResult:
        try:
            final_candidate_limit = self._config.resolve_candidate_limit(
                query.candidate_limit
            )
            candidate_result = self._candidate_retriever.retrieve(
                CandidateCvRetrievalQuery(
                    text=query.text,
                    candidate_limit=self._config.candidate_pool_limit,
                    semantic_result_limit=query.semantic_result_limit,
                    evidence_limit=self._config.candidate_evidence_pool_limit,
                )
            )
            return finalize_candidate_retrieval(
                query,
                candidate_result,
                config=self._config,
                candidate_limit=final_candidate_limit,
            )
        except (
            CvCandidateRetrievalError,
            CvRawRetrievalContractError,
            ValueError,
        ) as error:
            raise CvFinalRetrievalError(str(error)) from error


def finalize_candidate_retrieval(
    query: FinalCvRetrievalQuery,
    candidate_result: CandidateCvRetrievalResult,
    *,
    config: FinalRetrievalConfig,
    candidate_limit: int | None = None,
) -> FinalCvRetrievalResult:
    """Select supported candidates and construct bounded context deterministically."""

    resolved_limit = config.resolve_candidate_limit(candidate_limit)
    supported_pool, outcome = _select_support_pool(candidate_result, config=config)
    selected = supported_pool[:resolved_limit]

    if outcome == "unsupported":
        message = (
            "The indexed CV collection does not contain sufficiently supported "
            "evidence for this question."
        )
        context = _render_empty_context(query.text, message)
        return FinalCvRetrievalResult(
            query=query,
            candidate_result=candidate_result,
            outcome="unsupported",
            support_message=message,
            requested_candidate_limit=resolved_limit,
            max_total_evidence_chunks=config.max_total_evidence_chunks,
            max_context_characters=config.max_context_characters,
            candidates=(),
            context_text=context[: config.max_context_characters],
            budget_exhausted=False,
        )

    support_level: FinalSupportLevel = (
        "complete" if outcome == "supported" else "partial"
    )
    message = (
        "One or more candidates have complete source-backed coverage of the "
        "parsed recruiter requirements."
        if outcome == "supported"
        else "No candidate has complete coverage; the context contains only "
        "high-confidence partial matches and must be described as partial."
    )
    final_candidates, context, exhausted = _budget_candidates(
        query.text,
        selected,
        support_level=support_level,
        outcome=outcome,
        message=message,
        config=config,
    )
    if not final_candidates:
        unsupported_message = (
            "Candidate evidence met scoring thresholds but could not fit within "
            "the configured final context budget."
        )
        return FinalCvRetrievalResult(
            query=query,
            candidate_result=candidate_result,
            outcome="unsupported",
            support_message=unsupported_message,
            requested_candidate_limit=resolved_limit,
            max_total_evidence_chunks=config.max_total_evidence_chunks,
            max_context_characters=config.max_context_characters,
            candidates=(),
            context_text=_render_empty_context(
                query.text,
                unsupported_message,
            )[: config.max_context_characters],
            budget_exhausted=True,
        )

    return FinalCvRetrievalResult(
        query=query,
        candidate_result=candidate_result,
        outcome=outcome,
        support_message=message,
        requested_candidate_limit=resolved_limit,
        max_total_evidence_chunks=config.max_total_evidence_chunks,
        max_context_characters=config.max_context_characters,
        candidates=final_candidates,
        context_text=context,
        budget_exhausted=exhausted,
    )


def build_final_cv_retriever(settings: Settings) -> FinalCvRetriever:
    """Build the final WP6 retrieval boundary from application settings."""

    return FinalCvRetriever(
        FinalRetrievalConfig(
            default_candidate_limit=(
                settings.cv_final_retrieval_default_candidate_limit
            ),
            max_candidate_limit=settings.cv_final_retrieval_max_candidate_limit,
            candidate_pool_limit=settings.cv_final_retrieval_candidate_pool_limit,
            candidate_evidence_pool_limit=(
                settings.cv_final_retrieval_candidate_evidence_pool_limit
            ),
            evidence_per_candidate_limit=(
                settings.cv_final_retrieval_evidence_per_candidate_limit
            ),
            max_total_evidence_chunks=(
                settings.cv_final_retrieval_max_evidence_chunks
            ),
            max_context_characters=(
                settings.cv_final_retrieval_max_context_characters
            ),
            max_evidence_text_characters=(
                settings.cv_final_retrieval_max_evidence_characters
            ),
            complete_min_candidate_score=(
                settings.cv_final_retrieval_complete_min_score
            ),
            partial_min_candidate_score=(
                settings.cv_final_retrieval_partial_min_score
            ),
            partial_min_coverage=(
                settings.cv_final_retrieval_partial_min_coverage
            ),
        ),
        candidate_retriever=build_candidate_aware_cv_retriever(settings),
    )


def _select_support_pool(
    candidate_result: CandidateCvRetrievalResult,
    *,
    config: FinalRetrievalConfig,
) -> tuple[tuple[RankedCvCandidate, ...], FinalRetrievalOutcome]:
    complete = tuple(
        candidate
        for candidate in candidate_result.candidates
        if candidate.complete_condition_coverage
        and candidate.candidate_score >= config.complete_min_candidate_score
    )
    if complete:
        return complete, "supported"

    partial = tuple(
        candidate
        for candidate in candidate_result.candidates
        if candidate.matched_condition_count > 0
        and candidate.coverage_score >= config.partial_min_coverage
        and candidate.candidate_score >= config.partial_min_candidate_score
    )
    if partial:
        return partial, "partial"
    return (), "unsupported"


def _budget_candidates(
    question: str,
    candidates: tuple[RankedCvCandidate, ...],
    *,
    support_level: FinalSupportLevel,
    outcome: FinalRetrievalOutcome,
    message: str,
    config: FinalRetrievalConfig,
) -> tuple[tuple[FinalCvCandidate, ...], str, bool]:
    context_parts = [_context_preamble(question, outcome, message)]
    final_candidates: list[FinalCvCandidate] = []
    total_chunks = 0
    exhausted = False

    for candidate in candidates:
        if total_chunks >= config.max_total_evidence_chunks:
            exhausted = True
            break
        candidate_evidence = _prioritized_candidate_evidence(candidate)
        candidate_evidence = candidate_evidence[
            : config.evidence_per_candidate_limit
        ]
        candidate_header = _candidate_header(
            len(final_candidates) + 1,
            candidate,
            support_level=support_level,
        )
        remaining = config.max_context_characters - len("\n\n".join(context_parts))
        if remaining <= len(candidate_header) + 80:
            exhausted = True
            break

        evidence_objects: list[FinalCvEvidence] = []
        evidence_blocks: list[str] = []
        for selection in candidate_evidence:
            if total_chunks + len(evidence_objects) >= config.max_total_evidence_chunks:
                exhausted = True
                break
            evidence_order = len(evidence_objects) + 1
            metadata = _evidence_metadata(
                evidence_order,
                selection,
            )
            # Calculate against the exact rendered delimiters: two newlines
            # before the candidate block, one newline before every evidence
            # block, and ``\nEVIDENCE: `` between metadata and text.
            used_with_candidate = len(candidate_header) + sum(
                len(block) + 1 for block in evidence_blocks
            )
            current_context = len("\n\n".join(context_parts))
            available_text = (
                config.max_context_characters
                - current_context
                - 2
                - used_with_candidate
                - 1
                - len(metadata)
                - len("\nEVIDENCE: ")
            )
            text_limit = min(
                config.max_evidence_text_characters,
                available_text,
            )
            if text_limit < 40:
                exhausted = True
                break
            text = _truncate_evidence(selection.hit.text, text_limit)
            evidence = FinalCvEvidence(
                order=evidence_order,
                chunk_id=selection.hit.chunk_id,
                text=text,
                source=selection.hit.source,
                condition_keys=selection.condition_keys,
            )
            evidence_objects.append(evidence)
            evidence_blocks.append(f"{metadata}\nEVIDENCE: {text}")

        if not evidence_objects:
            exhausted = True
            break

        final_rank = len(final_candidates) + 1
        final_candidate = FinalCvCandidate(
            rank=final_rank,
            original_candidate_rank=candidate.rank,
            support_level=support_level,
            candidate_id=candidate.candidate_id,
            candidate_name=candidate.candidate_name,
            professional_title=candidate.professional_title,
            candidate_score=candidate.candidate_score,
            coverage_score=candidate.coverage_score,
            condition_quality_score=candidate.condition_quality_score,
            semantic_support_score=candidate.semantic_support_score,
            matched_condition_labels=tuple(
                match.condition.label for match in candidate.matched_conditions
            ),
            total_condition_count=candidate.total_condition_count,
            evidence=tuple(evidence_objects),
        )
        final_candidates.append(final_candidate)
        total_chunks += len(evidence_objects)
        context_parts.append(
            "\n".join([candidate_header, *evidence_blocks])
        )

    context = "\n\n".join(context_parts)
    if len(context) > config.max_context_characters:
        raise ValueError("Final context budgeting produced an oversized context.")
    if len(final_candidates) < len(candidates):
        exhausted = True
    return tuple(final_candidates), context, exhausted


def _prioritized_candidate_evidence(
    candidate: RankedCvCandidate,
) -> tuple[CandidateEvidenceSelection, ...]:
    return tuple(
        sorted(
            candidate.evidence,
            key=lambda item: (
                not bool(item.condition_keys),
                item.order,
                item.hit.rank,
            ),
        )
    )


def _context_preamble(
    question: str,
    outcome: FinalRetrievalOutcome,
    message: str,
) -> str:
    return (
        f"QUESTION: {question}\n"
        f"RETRIEVAL OUTCOME: {outcome}\n"
        f"QUALITY BOUNDARY: {message}"
    )


def _candidate_header(
    rank: int,
    candidate: RankedCvCandidate,
    *,
    support_level: FinalSupportLevel,
) -> str:
    name = candidate.candidate_name or "Unknown candidate"
    title = candidate.professional_title or "Unknown title"
    matched = "; ".join(
        match.condition.label for match in candidate.matched_conditions
    ) or "none"
    return (
        f"CANDIDATE {rank}: {name} | {title} | {candidate.candidate_id}\n"
        f"SUPPORT: {support_level} | candidate_score="
        f"{candidate.candidate_score:.4f} | coverage="
        f"{candidate.coverage_score:.4f}\n"
        f"MATCHED REQUIREMENTS: {matched}"
    )


def _evidence_metadata(
    order: int,
    selection: CandidateEvidenceSelection,
) -> str:
    source = selection.hit.source
    supports = ", ".join(selection.condition_keys) or "support-only"
    return (
        f"SOURCE {order}: {source.source_filename} | page "
        f"{source.page_label} | {source.section_name} | "
        f"{selection.hit.chunk_id}\nSUPPORTS: {supports}"
    )


def _truncate_evidence(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    if limit <= 3:
        return normalized[:limit]
    return normalized[: limit - 3].rstrip() + "..."


def _render_empty_context(question: str, message: str) -> str:
    return (
        f"QUESTION: {question}\n"
        "RETRIEVAL OUTCOME: unsupported\n"
        f"QUALITY BOUNDARY: {message}\n"
        "CANDIDATES: none"
    )
