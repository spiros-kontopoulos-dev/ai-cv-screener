"""Tests for support-aware grounded answer orchestration."""

from collections.abc import Sequence

import pytest

from app.cv_answer_generation import (
    GroundedAnswerDraft,
    GroundedAnswerGenerationConfig,
    GroundedAnswerGenerationFailed,
    GroundedAnswerProviderError,
    GroundedCandidateAnswer,
    GroundedCvAnswerGenerator,
    validate_grounded_answer_draft,
)
from app.cv_retrieval import FinalCvRetrievalQuery
from cv_retrieval_test_helpers import CandidateSpec, build_candidate_result, finalize_for_test


class FakeFinalRetriever:
    def __init__(self, result):
        self.result = result
        self.queries = []

    def retrieve(self, query):
        self.queries.append(query)
        return self.result


class SequenceProvider:
    def __init__(self, responses: Sequence[object]):
        self.responses = list(responses)
        self.calls = []

    def generate(self, retrieval_result, *, correction_feedback=()):
        self.calls.append(tuple(correction_feedback))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _supported_result():
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


def _partial_result():
    return finalize_for_test(
        build_candidate_result(
            (
                CandidateSpec(
                    "candidate_002",
                    "Jonas Keller",
                    "Python Backend Engineer",
                    matched_count=2,
                    candidate_score=0.55,
                    coverage_score=2 / 3,
                ),
            ),
            condition_labels=("backend engineer", "german", "native"),
        )
    )


def _unsupported_result():
    return finalize_for_test(
        build_candidate_result(
            (
                CandidateSpec(
                    "candidate_noise",
                    "Noise Candidate",
                    "Engineer",
                    matched_count=0,
                    candidate_score=0.2,
                    coverage_score=0.0,
                ),
            ),
            question="Who holds government security clearance?",
            condition_labels=("government", "security", "clearance"),
        )
    )


def _draft_for(result, *, limitations=None) -> GroundedAnswerDraft:
    return GroundedAnswerDraft(
        outcome=result.outcome,
        answer="The retrieved candidates are explained using the supplied evidence.",
        candidates=[
            GroundedCandidateAnswer(
                candidate_id=candidate.candidate_id,
                candidate_name=candidate.candidate_name or "Unknown candidate",
                professional_title=(
                    candidate.professional_title or "Unknown title"
                ),
                assessment="The supplied evidence supports the matched requirements.",
                matched_requirements=list(candidate.matched_condition_labels),
            )
            for candidate in result.candidates
        ],
        limitations=(
            limitations
            if limitations is not None
            else (["No candidate has complete coverage."] if result.outcome == "partial" else [])
        ),
    )


def _generator(result, provider, *, max_retries=1):
    return GroundedCvAnswerGenerator(
        GroundedAnswerGenerationConfig(max_retries=max_retries),
        retriever=FakeFinalRetriever(result),
        provider=provider,
        model_name="gpt-test",
    )


def test_supported_answer_is_accepted_with_exact_candidate_order() -> None:
    retrieval = _supported_result()
    provider = SequenceProvider([_draft_for(retrieval)])

    result = _generator(retrieval, provider).generate(
        FinalCvRetrievalQuery("Python and PostgreSQL")
    )

    assert result.draft.outcome == "supported"
    assert [item.candidate_id for item in result.draft.candidates] == [
        "candidate_001",
        "candidate_011",
    ]
    assert result.attempts == 1
    assert result.provider_called is True


def test_partial_answer_requires_an_explicit_limitation() -> None:
    retrieval = _partial_result()
    draft = _draft_for(retrieval, limitations=[])

    problems = validate_grounded_answer_draft(
        draft,
        retrieval,
        config=GroundedAnswerGenerationConfig(),
    )

    assert "Partial answers must include" in " ".join(problems)


def test_unsupported_result_skips_the_llm_and_returns_honest_answer() -> None:
    retrieval = _unsupported_result()
    provider = SequenceProvider([])

    result = _generator(retrieval, provider).generate(
        FinalCvRetrievalQuery("Government security clearance")
    )

    assert result.draft.outcome == "unsupported"
    assert result.draft.candidates == []
    assert result.provider_called is False
    assert result.attempts == 0
    assert provider.calls == []


def test_invented_or_reordered_candidate_triggers_bounded_correction() -> None:
    retrieval = _supported_result()
    invalid = _draft_for(retrieval)
    invalid.candidates.reverse()
    valid = _draft_for(retrieval)
    provider = SequenceProvider([invalid, valid])

    result = _generator(retrieval, provider).generate(
        FinalCvRetrievalQuery("Python and PostgreSQL")
    )

    assert result.attempts == 2
    assert provider.calls[0] == ()
    assert "exactly match retrieval order" in " ".join(provider.calls[1])


def test_candidate_metadata_and_requirements_are_immutable() -> None:
    retrieval = _supported_result()
    draft = _draft_for(retrieval)
    draft.candidates[0].candidate_name = "Invented Name"
    draft.candidates[0].matched_requirements = ["python", "aws"]

    problems = validate_grounded_answer_draft(
        draft,
        retrieval,
        config=GroundedAnswerGenerationConfig(),
    )

    joined = " ".join(problems)
    assert "name must remain" in joined
    assert "matched requirements must remain" in joined


def test_output_character_limits_are_enforced() -> None:
    retrieval = _supported_result()
    draft = _draft_for(retrieval)
    draft.answer = "A" * 501
    draft.candidates[0].assessment = "B" * 301

    problems = validate_grounded_answer_draft(
        draft,
        retrieval,
        config=GroundedAnswerGenerationConfig(
            max_answer_characters=500,
            max_candidate_assessment_characters=300,
        ),
    )

    assert any("Overall answer exceeds" in problem for problem in problems)
    assert any("assessment exceeds" in problem for problem in problems)


def test_exhausted_validation_retries_raise_actionable_failure() -> None:
    retrieval = _supported_result()
    invalid = _draft_for(retrieval)
    invalid.candidates = invalid.candidates[:1]
    provider = SequenceProvider([invalid, invalid])

    with pytest.raises(GroundedAnswerGenerationFailed) as raised:
        _generator(retrieval, provider).generate(
            FinalCvRetrievalQuery("Python and PostgreSQL")
        )

    assert raised.value.attempts == 2
    assert "exactly match retrieval order" in str(raised.value)


def test_non_retryable_provider_failure_stops_immediately() -> None:
    retrieval = _supported_result()
    provider = SequenceProvider(
        [GroundedAnswerProviderError("provider rejected request", retryable=False)]
    )

    with pytest.raises(GroundedAnswerGenerationFailed) as raised:
        _generator(retrieval, provider).generate(
            FinalCvRetrievalQuery("Python and PostgreSQL")
        )

    assert raised.value.attempts == 1
    assert "provider rejected request" in str(raised.value)


def test_supported_evidence_requires_a_configured_provider() -> None:
    retrieval = _supported_result()

    with pytest.raises(GroundedAnswerGenerationFailed) as raised:
        _generator(retrieval, None).generate(
            FinalCvRetrievalQuery("Python and PostgreSQL")
        )

    assert raised.value.attempts == 0
    assert "OPENAI_API_KEY" in str(raised.value)
