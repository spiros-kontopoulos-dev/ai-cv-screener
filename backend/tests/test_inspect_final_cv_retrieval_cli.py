"""CLI tests for final support and context-budget inspection."""

from app.scripts.inspect_final_cv_retrieval import run_cli
from cv_retrieval_test_helpers import (
    CandidateSpec,
    build_candidate_result,
    finalize_for_test,
)


class FakeFinalRetriever:
    def __init__(self, result):
        self.result = result

    def retrieve(self, query):
        return self.result


def _retriever():
    result = finalize_for_test(
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
    return FakeFinalRetriever(result)


def test_cli_prints_outcome_budgets_sources_and_prompt_context(capsys) -> None:
    status = run_cli(
        [
            "--query",
            "Find Python and PostgreSQL candidates.",
            "--show-context",
        ],
        retriever=_retriever(),
    )
    output = capsys.readouterr().out

    assert status == 0
    assert "FINAL CV RETRIEVAL INSPECTION" in output
    assert "Outcome: supported" in output
    assert "Evidence chunks:" in output
    assert "Context characters:" in output
    assert "candidate=candidate_001" in output
    assert "candidate_001-cv.pdf" in output
    assert "PROMPT-READY CONTEXT" in output


def test_cli_rejects_negative_preview_limit(capsys) -> None:
    status = run_cli(
        ["--query", "Python", "--preview-characters", "-1"],
        retriever=_retriever(),
    )

    assert status == 2
    assert "cannot be negative" in capsys.readouterr().err
