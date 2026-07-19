"""CLI tests for end-to-end final retrieval scenario validation."""

import json
from types import SimpleNamespace

from app.scripts.validate_cv_retrieval import run_cli
from cv_retrieval_test_helpers import (
    CandidateSpec,
    build_candidate_result,
    finalize_for_test,
)


class MappingFinalRetriever:
    def __init__(self, results):
        self.results = results

    def retrieve(self, query):
        return self.results[query.text]


def _plan(tmp_path):
    path = tmp_path / "plan.json"
    path.write_text(
        json.dumps(
            {
                "search_scenarios": [
                    {
                        "scenario_id": "python",
                        "question": "Find Python and PostgreSQL candidates.",
                        "expected_candidate_ids": ["candidate_001"],
                        "required_evidence": ["Python", "PostgreSQL"],
                        "answer_behavior": "Return the candidate.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def test_cli_prints_passing_scenario_report(tmp_path, capsys) -> None:
    plan = _plan(tmp_path)
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
    retriever = MappingFinalRetriever(
        {"Find Python and PostgreSQL candidates.": result}
    )

    status = run_cli(
        [],
        settings=SimpleNamespace(candidate_dataset_plan_path=plan),
        retriever=retriever,
    )
    output = capsys.readouterr().out

    assert status == 0
    assert "FINAL CV RETRIEVAL VALIDATION" in output
    assert "Scenarios: 1" in output
    assert "Result: PASS" in output
    assert "[PASS] python" in output


def test_cli_returns_failure_for_missing_expected_candidate(tmp_path, capsys) -> None:
    plan = _plan(tmp_path)
    result = finalize_for_test(
        build_candidate_result(
            (
                CandidateSpec(
                    "candidate_999",
                    "Wrong Candidate",
                    "Python Engineer",
                    matched_count=2,
                    candidate_score=0.9,
                    coverage_score=1.0,
                ),
            )
        )
    )
    retriever = MappingFinalRetriever(
        {"Find Python and PostgreSQL candidates.": result}
    )

    status = run_cli(
        [],
        settings=SimpleNamespace(candidate_dataset_plan_path=plan),
        retriever=retriever,
    )
    output = capsys.readouterr().out

    assert status == 1
    assert "Result: FAIL" in output
    assert "missing=candidate_001" in output
