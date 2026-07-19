"""Convert validated WP7 domain results into the frozen WP8 API contract."""

from app.cv_answer_generation import (
    GroundedAnswerGenerationResult,
    build_source_id,
)

from .schemas import ChatCandidate, ChatResponse, ChatSource


def present_chat_response(
    result: GroundedAnswerGenerationResult,
) -> ChatResponse:
    """Add ranking and page fields without weakening WP7 source validation."""

    response = result.response
    retrieval = result.retrieval_result
    retrieval_by_id = {
        candidate.candidate_id: candidate for candidate in retrieval.candidates
    }
    evidence_by_source_id = {
        build_source_id(candidate.candidate_id, evidence.order): evidence
        for candidate in retrieval.candidates
        for evidence in candidate.evidence
    }

    candidates = []
    for candidate_answer in response.candidates:
        ranked = retrieval_by_id[candidate_answer.candidate_id]
        candidates.append(
            ChatCandidate(
                candidate_id=candidate_answer.candidate_id,
                name=candidate_answer.candidate_name,
                professional_title=candidate_answer.professional_title,
                rank=ranked.rank,
                support_level=ranked.support_level,
                relevance_score=ranked.candidate_score,
                coverage_score=ranked.coverage_score,
                matched_requirements=candidate_answer.matched_requirements,
                assessment=candidate_answer.assessment,
                citation_ids=candidate_answer.citation_ids,
            )
        )

    sources = []
    for source in response.sources:
        evidence = evidence_by_source_id[source.source_id]
        sources.append(
            ChatSource(
                source_id=source.source_id,
                candidate_id=source.candidate_id,
                candidate_name=source.candidate_name,
                filename=source.source_filename,
                page=evidence.source.page_number_start,
                page_label=source.page_label,
                section=source.section_name,
                chunk_id=source.chunk_id,
                supports=source.supports,
                text=source.evidence_excerpt,
                cv_url=f"/api/candidates/{source.candidate_id}/cv",
            )
        )

    # Hosted providers may phrase reassurance (for example, "no partial
    # coverage") as a limitation. A fully supported hosted answer is not a
    # degraded state, so the browser contract suppresses those free-form
    # limitations. Deterministic, partial, and unsupported warnings remain
    # visible because they describe real application behavior.
    warnings = (
        []
        if response.outcome == "supported" and response.provider_called
        else response.warnings
    )

    return ChatResponse(
        question=retrieval.query.text,
        outcome=response.outcome,
        answer=response.answer,
        provider=response.provider,
        model=response.model,
        provider_called=response.provider_called,
        provider_attempts=response.provider_attempts,
        answer_citation_ids=response.answer_citation_ids,
        candidates=candidates,
        sources=sources,
        warnings=warnings,
    )
