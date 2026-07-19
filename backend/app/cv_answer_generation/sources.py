"""Deterministic source registry and citation validation for grounded answers."""

from app.cv_retrieval import FinalCvCandidate, FinalCvRetrievalResult

from .models import GroundedAnswerDraft, GroundedAnswerSource


def build_source_id(candidate_id: str, evidence_order: int) -> str:
    """Return a stable source identifier safe for prompts and API responses."""

    return f"{candidate_id}-source-{evidence_order}"


def build_grounded_answer_sources(
    retrieval_result: FinalCvRetrievalResult,
) -> tuple[GroundedAnswerSource, ...]:
    """Convert final WP6 evidence into a deterministic source registry."""

    labels_by_key = {
        condition.key: condition.label
        for condition in retrieval_result.candidate_result.conditions
    }
    sources: list[GroundedAnswerSource] = []

    for candidate in retrieval_result.candidates:
        candidate_name = candidate.candidate_name or "Unknown candidate"
        for evidence in candidate.evidence:
            supports = [
                labels_by_key[key]
                for key in evidence.condition_keys
                if key in labels_by_key
            ]
            sources.append(
                GroundedAnswerSource(
                    source_id=build_source_id(candidate.candidate_id, evidence.order),
                    candidate_id=candidate.candidate_id,
                    candidate_name=candidate_name,
                    source_filename=evidence.source.source_filename,
                    page_label=evidence.source.page_label,
                    section_name=evidence.source.section_name,
                    chunk_id=evidence.chunk_id,
                    supports=supports,
                    evidence_excerpt=evidence.text,
                )
            )

    return tuple(sources)


def default_candidate_citation_ids(
    candidate: FinalCvCandidate,
) -> tuple[str, ...]:
    """Choose concise direct evidence citations for deterministic responses."""

    direct = [
        build_source_id(candidate.candidate_id, evidence.order)
        for evidence in candidate.evidence
        if evidence.condition_keys
    ]
    if direct:
        return tuple(direct)
    return (build_source_id(candidate.candidate_id, candidate.evidence[0].order),)


def validate_grounded_answer_citations(
    draft: GroundedAnswerDraft,
    retrieval_result: FinalCvRetrievalResult,
) -> list[str]:
    """Reject unknown, cross-candidate, or requirement-incomplete citations."""

    problems: list[str] = []
    sources = build_grounded_answer_sources(retrieval_result)
    source_by_id = {source.source_id: source for source in sources}

    if retrieval_result.outcome == "unsupported":
        if draft.answer_citation_ids:
            problems.append("Unsupported answers cannot include answer citations.")
        return problems

    if not draft.answer_citation_ids:
        problems.append("Supported and partial answers require answer citations.")

    unknown_answer_ids = [
        source_id
        for source_id in draft.answer_citation_ids
        if source_id not in source_by_id
    ]
    if unknown_answer_ids:
        problems.append(
            "Answer citations contain unknown source IDs: "
            + ", ".join(unknown_answer_ids)
            + "."
        )

    expected_candidate_ids = {
        candidate.candidate_id for candidate in retrieval_result.candidates
    }
    cited_answer_candidate_ids = {
        source_by_id[source_id].candidate_id
        for source_id in draft.answer_citation_ids
        if source_id in source_by_id
    }
    missing_answer_candidates = sorted(
        expected_candidate_ids - cited_answer_candidate_ids
    )
    if missing_answer_candidates:
        problems.append(
            "Overall answer citations must include every returned candidate: "
            + ", ".join(missing_answer_candidates)
            + "."
        )

    expected_by_id = {
        candidate.candidate_id: candidate
        for candidate in retrieval_result.candidates
    }
    for candidate_draft in draft.candidates:
        expected = expected_by_id.get(candidate_draft.candidate_id)
        if expected is None:
            continue

        unknown_ids = [
            source_id
            for source_id in candidate_draft.citation_ids
            if source_id not in source_by_id
        ]
        if unknown_ids:
            problems.append(
                f"{candidate_draft.candidate_id} citations contain unknown "
                "source IDs: " + ", ".join(unknown_ids) + "."
            )
            continue

        cross_candidate_ids = [
            source_id
            for source_id in candidate_draft.citation_ids
            if source_by_id[source_id].candidate_id
            != candidate_draft.candidate_id
        ]
        if cross_candidate_ids:
            problems.append(
                f"{candidate_draft.candidate_id} citations cross candidate "
                "boundaries: " + ", ".join(cross_candidate_ids) + "."
            )

        cited_supports = {
            label
            for source_id in candidate_draft.citation_ids
            if source_id in source_by_id
            and source_by_id[source_id].candidate_id
            == candidate_draft.candidate_id
            for label in source_by_id[source_id].supports
        }
        missing_requirements = [
            label
            for label in expected.matched_condition_labels
            if label not in cited_supports
        ]
        if missing_requirements:
            problems.append(
                f"{candidate_draft.candidate_id} citations do not cover matched "
                "requirements: " + ", ".join(missing_requirements) + "."
            )

    return problems
