"""CLI tests for grounded answer inspection."""

from app.cv_answer_generation import (
    GroundedAnswerDraft,
    GroundedAnswerGenerationResult,
    GroundedCandidateAnswer,
)
from app.core.config import Settings
from app.scripts.inspect_grounded_cv_answer import run_cli
from cv_retrieval_test_helpers import CandidateSpec, build_candidate_result, finalize_for_test


class FakeGenerator:
    def __init__(self, result):
        self.result = result

    def generate(self, query):
        return self.result


def _result():
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
            )
        )
    )
    draft = GroundedAnswerDraft(
        outcome="supported",
        answer="Eleni is a complete evidence-backed match.",
        answer_citation_ids=["candidate_001-source-1"],
        candidates=[
            GroundedCandidateAnswer(
                candidate_id="candidate_001",
                candidate_name="Eleni Markou",
                professional_title="Senior Python Backend Engineer",
                assessment="Her CV supports the requested requirements.",
                matched_requirements=["python", "postgresql"],
                citation_ids=["candidate_001-source-1"],
            )
        ],
        limitations=[],
    )
    return GroundedAnswerGenerationResult(
        retrieval_result=retrieval,
        draft=draft,
        attempts=1,
        provider_called=True,
        model_name="gpt-test",
        provider_name="openai",
    )


def test_cli_prints_answer_candidates_and_optional_context(capsys) -> None:
    status = run_cli(
        ["--query", "Python and PostgreSQL", "--show-context"],
        settings=Settings(cv_grounded_answer_model="gpt-test"),
        generator=FakeGenerator(_result()),
    )
    output = capsys.readouterr().out

    assert status == 0
    assert "GROUNDED CV ANSWER INSPECTION" in output
    assert "Answer outcome: supported" in output
    assert "Eleni is a complete evidence-backed match" in output
    assert "candidate_001" in output
    assert "Active provider: openai" in output
    assert "candidate_001-source-1" in output
    assert "SOURCES" in output
    assert "RETRIEVAL CONTEXT SUPPLIED TO MODEL" in output


def test_cli_rejects_invalid_query_limit(capsys) -> None:
    status = run_cli(
        ["--query", "Python", "--candidate-limit", "0"],
        settings=Settings(cv_grounded_answer_model="gpt-test"),
        generator=FakeGenerator(_result()),
    )

    assert status == 2
    assert "must be positive" in capsys.readouterr().err
