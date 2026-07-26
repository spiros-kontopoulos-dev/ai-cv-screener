"""Convert internal search-and-answer results into the public chat response.

The retrieval and answer modules use detailed domain models. The React client
needs one stable response shape with candidate scores, source pages, and CV
links. This file joins those already-validated results without running another
search or changing which evidence was accepted.
"""

from app.cv_answer_generation import (
    GroundedAnswerGenerationResult,
    build_source_id,
)

from .schemas import ChatCandidate, ChatResponse, ChatSource


def present_chat_response(
    result: GroundedAnswerGenerationResult,
) -> ChatResponse:
    """Build the JSON-ready chat response used by the frontend.

    The answer result already contains validated candidate names, citations,
    and source ownership. The retrieval result adds values that the UI also
    needs, such as ranking scores and the first page of each evidence chunk.
    The two collections are joined by candidate ID and source ID.
    """

    response = result.response
    retrieval = result.retrieval_result

    # These lookups avoid repeatedly scanning the result lists while we build
    # the public candidate and source objects.
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

    # A hosted model can sometimes return a harmless note such as "no partial
    # matches" even when the answer is fully supported. The UI hides those
    # notes. Real warnings for deterministic, partial, or unsupported answers
    # remain visible.
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
