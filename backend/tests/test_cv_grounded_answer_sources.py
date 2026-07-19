"""Tests for claim-level source references and final answer responses."""

from app.cv_answer_generation import (
    GroundedAnswerDraft,
    GroundedAnswerGenerationConfig,
    GroundedAnswerGenerationResult,
    GroundedCandidateAnswer,
    build_grounded_answer_sources,
    validate_grounded_answer_draft,
)
from cv_retrieval_test_helpers import CandidateSpec, build_candidate_result, finalize_for_test


def _retrieval(*, evidence_texts=("Direct evidence.", "Supporting detail.")):
    return finalize_for_test(
        build_candidate_result(
            (
                CandidateSpec(
                    "candidate_001",
                    "Eleni Markou",
                    "Senior Python Backend Engineer",
                    matched_count=2,
                    candidate_score=0.9,
                    coverage_score=1.0,
                    evidence_texts=evidence_texts,
                ),
            )
        )
    )


def _draft(citation_ids=None) -> GroundedAnswerDraft:
    citations = citation_ids or ["candidate_001-source-1"]
    return GroundedAnswerDraft(
        outcome="supported",
        answer="Eleni is a complete source-backed match.",
        answer_citation_ids=list(citations),
        candidates=[
            GroundedCandidateAnswer(
                candidate_id="candidate_001",
                candidate_name="Eleni Markou",
                professional_title="Senior Python Backend Engineer",
                assessment="Her evidence supports Python and PostgreSQL.",
                matched_requirements=["python", "postgresql"],
                citation_ids=list(citations),
            )
        ],
        limitations=[],
    )


def test_source_registry_preserves_pdf_provenance_and_support_labels() -> None:
    sources = build_grounded_answer_sources(_retrieval())

    assert [source.source_id for source in sources] == [
        "candidate_001-source-1",
        "candidate_001-source-2",
    ]
    assert sources[0].source_filename == "candidate_001-cv.pdf"
    assert sources[0].page_label == "1"
    assert sources[0].section_name == "experience"
    assert sources[0].supports == ["python", "postgresql"]
    assert sources[1].supports == []


def test_unknown_citation_is_rejected() -> None:
    problems = validate_grounded_answer_draft(
        _draft(["invented-source"]),
        _retrieval(),
        config=GroundedAnswerGenerationConfig(),
    )

    assert "unknown source IDs" in " ".join(problems)


def test_support_only_citation_cannot_claim_requirement_coverage() -> None:
    problems = validate_grounded_answer_draft(
        _draft(["candidate_001-source-2"]),
        _retrieval(),
        config=GroundedAnswerGenerationConfig(),
    )

    assert "do not cover matched requirements" in " ".join(problems)


def test_final_response_exposes_only_referenced_sources() -> None:
    retrieval = _retrieval()
    result = GroundedAnswerGenerationResult(
        retrieval_result=retrieval,
        draft=_draft(["candidate_001-source-1"]),
        attempts=1,
        provider_called=True,
        model_name="gpt-test",
        provider_name="openai",
    )

    response = result.response

    assert response.provider == "openai"
    assert [source.source_id for source in response.sources] == [
        "candidate_001-source-1"
    ]
    assert response.warnings == []


def test_deterministic_response_includes_mode_warning() -> None:
    retrieval = _retrieval(evidence_texts=("Direct evidence.",))
    result = GroundedAnswerGenerationResult(
        retrieval_result=retrieval,
        draft=_draft(),
        attempts=0,
        provider_called=False,
        model_name="deterministic-template-v1",
        provider_name="deterministic",
    )

    assert "deterministic no-key fallback" in " ".join(result.response.warnings)


def test_cross_candidate_citation_is_rejected() -> None:
    retrieval = finalize_for_test(
        build_candidate_result(
            (
                CandidateSpec(
                    "candidate_001",
                    "Eleni Markou",
                    "Senior Python Backend Engineer",
                    matched_count=2,
                    candidate_score=0.9,
                    coverage_score=1.0,
                ),
                CandidateSpec(
                    "candidate_011",
                    "Mila Stoyanova",
                    "Junior Full-Stack Engineer",
                    matched_count=2,
                    candidate_score=0.85,
                    coverage_score=1.0,
                ),
            )
        )
    )
    draft = GroundedAnswerDraft(
        outcome="supported",
        answer="Two candidates match.",
        answer_citation_ids=[
            "candidate_001-source-1",
            "candidate_011-source-1",
        ],
        candidates=[
            GroundedCandidateAnswer(
                candidate_id="candidate_001",
                candidate_name="Eleni Markou",
                professional_title="Senior Python Backend Engineer",
                assessment="Eleni matches.",
                matched_requirements=["python", "postgresql"],
                citation_ids=["candidate_011-source-1"],
            ),
            GroundedCandidateAnswer(
                candidate_id="candidate_011",
                candidate_name="Mila Stoyanova",
                professional_title="Junior Full-Stack Engineer",
                assessment="Mila matches.",
                matched_requirements=["python", "postgresql"],
                citation_ids=["candidate_011-source-1"],
            ),
        ],
        limitations=[],
    )

    problems = validate_grounded_answer_draft(
        draft,
        retrieval,
        config=GroundedAnswerGenerationConfig(),
    )

    assert "cross candidate boundaries" in " ".join(problems)


def test_overall_answer_must_cite_every_returned_candidate() -> None:
    retrieval = finalize_for_test(
        build_candidate_result(
            (
                CandidateSpec(
                    "candidate_001",
                    "Eleni Markou",
                    "Senior Python Backend Engineer",
                    matched_count=2,
                    candidate_score=0.9,
                    coverage_score=1.0,
                ),
                CandidateSpec(
                    "candidate_011",
                    "Mila Stoyanova",
                    "Junior Full-Stack Engineer",
                    matched_count=2,
                    candidate_score=0.85,
                    coverage_score=1.0,
                ),
            )
        )
    )
    draft = GroundedAnswerDraft(
        outcome="supported",
        answer="Two candidates match.",
        answer_citation_ids=["candidate_001-source-1"],
        candidates=[
            GroundedCandidateAnswer(
                candidate_id=candidate.candidate_id,
                candidate_name=candidate.candidate_name or "Unknown candidate",
                professional_title=candidate.professional_title or "Unknown title",
                assessment="The candidate matches.",
                matched_requirements=list(candidate.matched_condition_labels),
                citation_ids=[f"{candidate.candidate_id}-source-1"],
            )
            for candidate in retrieval.candidates
        ],
        limitations=[],
    )

    problems = validate_grounded_answer_draft(
        draft,
        retrieval,
        config=GroundedAnswerGenerationConfig(),
    )

    assert "must include every returned candidate" in " ".join(problems)
