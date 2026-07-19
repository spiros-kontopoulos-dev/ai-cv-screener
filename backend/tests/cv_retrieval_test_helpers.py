"""Small deterministic builders shared by final-retrieval tests."""

from dataclasses import dataclass

from app.cv_retrieval import (
    AssistedCvRetrievalResult,
    CandidateConditionMatch,
    CandidateCvRetrievalResult,
    CandidateEvidenceSelection,
    CandidateQueryCondition,
    CvEvidenceScore,
    FinalCvRetrievalQuery,
    FinalCvRetrievalResult,
    FinalRetrievalConfig,
    RankedCvCandidate,
    RawCvRetrievalQuery,
    RawCvRetrievalResult,
    RawCvRetrievalSource,
    ScoredCvEvidenceHit,
    analyze_recruiter_question,
    finalize_candidate_retrieval,
)


@dataclass(frozen=True)
class CandidateSpec:
    candidate_id: str
    name: str
    title: str
    matched_count: int
    candidate_score: float
    coverage_score: float
    evidence_texts: tuple[str, ...] = ("Source-backed candidate evidence.",)


def build_candidate_result(
    specs: tuple[CandidateSpec, ...],
    *,
    question: str = "Find Python and PostgreSQL candidates.",
    condition_labels: tuple[str, ...] = ("python", "postgresql"),
) -> CandidateCvRetrievalResult:
    conditions = tuple(
        CandidateQueryCondition(
            key=f"term:{label}",
            label=label,
            kind="term",
            weight=1.0,
            terms=(label,),
        )
        for label in condition_labels
    )
    hits: list[ScoredCvEvidenceHit] = []
    candidates: list[RankedCvCandidate] = []
    rank = 1

    for candidate_rank, spec in enumerate(specs, start=1):
        candidate_hits: list[ScoredCvEvidenceHit] = []
        for evidence_index, text in enumerate(spec.evidence_texts, start=1):
            hit = _hit(
                rank=rank,
                candidate_id=spec.candidate_id,
                candidate_name=spec.name,
                title=spec.title,
                text=text,
                chunk_suffix=str(evidence_index),
            )
            hits.append(hit)
            candidate_hits.append(hit)
            rank += 1

        matched = tuple(
            CandidateConditionMatch(
                condition=condition,
                chunk_id=candidate_hits[0].chunk_id,
                assisted_rank=candidate_hits[0].rank,
                evidence_score=0.9,
            )
            for condition in conditions[: spec.matched_count]
        )
        evidence = tuple(
            CandidateEvidenceSelection(
                order=index,
                hit=hit,
                condition_keys=(
                    tuple(match.condition.key for match in matched)
                    if index == 1
                    else ()
                ),
            )
            for index, hit in enumerate(candidate_hits, start=1)
        )
        candidates.append(
            RankedCvCandidate(
                rank=candidate_rank,
                candidate_id=spec.candidate_id,
                candidate_name=spec.name,
                professional_title=spec.title,
                candidate_score=spec.candidate_score,
                coverage_score=spec.coverage_score,
                condition_quality_score=(
                    0.9 * spec.matched_count / max(len(conditions), 1)
                ),
                semantic_support_score=0.7,
                matched_conditions=matched,
                total_condition_count=len(conditions),
                total_candidate_hit_count=len(candidate_hits),
                evidence=evidence,
            )
        )

    raw_query = RawCvRetrievalQuery(question, result_limit=50)
    raw = RawCvRetrievalResult(
        query=raw_query,
        requested_result_limit=50,
        collection_name="cv_chunks",
        collection_record_count=184,
        distance_metric="cosine",
        embedding_model="test-model",
        embedding_dimension=384,
        hits=(),
    )
    assisted = AssistedCvRetrievalResult(
        raw_result=raw,
        query_features=analyze_recruiter_question(question),
        scanned_record_count=184,
        duplicates_removed=0,
        supplemental_hit_count=0,
        hits=tuple(hits),
    )
    return CandidateCvRetrievalResult(
        assisted_result=assisted,
        conditions=conditions,
        requested_candidate_limit=max(len(candidates), 1),
        evidence_per_candidate_limit=max(
            max((len(candidate.evidence) for candidate in candidates), default=1),
            1,
        ),
        grouped_candidate_count=len(candidates),
        candidates=tuple(candidates),
    )


def finalize_for_test(
    candidate_result: CandidateCvRetrievalResult,
    *,
    question: str | None = None,
    config: FinalRetrievalConfig | None = None,
    candidate_limit: int | None = None,
) -> FinalCvRetrievalResult:
    query_text = question or candidate_result.assisted_result.raw_result.query.text
    return finalize_candidate_retrieval(
        FinalCvRetrievalQuery(query_text),
        candidate_result,
        config=config or FinalRetrievalConfig(),
        candidate_limit=candidate_limit,
    )


def _hit(
    *,
    rank: int,
    candidate_id: str,
    candidate_name: str,
    title: str,
    text: str,
    chunk_suffix: str,
) -> ScoredCvEvidenceHit:
    source = RawCvRetrievalSource(
        candidate_id=candidate_id,
        candidate_name=candidate_name,
        professional_title=title,
        document_id=f"document_{candidate_id}",
        document_hash=(candidate_id.replace("_", "") + "a" * 64)[:64],
        source_filename=f"{candidate_id}-cv.pdf",
        source_path=f"/app/data/cv_pdfs/{candidate_id}-cv.pdf",
        section_name="experience",
        page_numbers=(1,),
        chunk_index=rank,
        chunking_version="cv-sections-v1",
    )
    return ScoredCvEvidenceHit(
        rank=rank,
        raw_rank=rank,
        chunk_id=f"chunk_{candidate_id}_{chunk_suffix}",
        distance=0.3,
        text=text,
        source=source,
        score=CvEvidenceScore(
            semantic_score=0.7,
            lexical_score=0.9,
            numeric_score=0.0,
            combined_score=0.8,
            matched_terms=("python", "postgresql"),
            matched_phrases=(),
            matched_numeric_values=(),
            contextual_numeric_match=False,
        ),
    )
