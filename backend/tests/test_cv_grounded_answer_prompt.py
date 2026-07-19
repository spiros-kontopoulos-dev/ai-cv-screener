"""Tests for deterministic grounded-answer prompt construction."""

from app.cv_answer_generation import (
    GROUNDED_ANSWER_INSTRUCTIONS,
    build_grounded_answer_prompt,
)
from cv_retrieval_test_helpers import CandidateSpec, build_candidate_result, finalize_for_test


def _retrieval_result():
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
                ),
            )
        )
    )


def test_prompt_contains_question_registry_and_bounded_context() -> None:
    result = _retrieval_result()

    prompt = build_grounded_answer_prompt(result)

    assert result.query.text in prompt
    assert '"candidate_id": "candidate_001"' in prompt
    assert '"candidate_name": "Eleni Markou"' in prompt
    assert '"matched_requirements": [' in prompt
    assert '"source_id": "candidate_001-source-1"' in prompt
    assert result.context_text in prompt


def test_prompt_adds_exact_correction_feedback() -> None:
    prompt = build_grounded_answer_prompt(
        _retrieval_result(),
        correction_feedback=("Do not invent candidate_999.",),
    )

    assert "previous structured draft failed" in prompt
    assert "- Do not invent candidate_999." in prompt


def test_shared_instructions_define_the_grounding_boundary() -> None:
    assert "Use only the supplied RETRIEVAL CONTEXT" in GROUNDED_ANSWER_INSTRUCTIONS
    assert "Never add, remove, merge, rename, or reorder candidates" in (
        GROUNDED_ANSWER_INSTRUCTIONS
    )
    assert "Do not use outside knowledge" in GROUNDED_ANSWER_INSTRUCTIONS
    assert "Cite only source_id values" in GROUNDED_ANSWER_INSTRUCTIONS
