"""Tests for committed final-retrieval scenario evaluation."""

import json
from pathlib import Path

import pytest

from app.cv_retrieval import (
    CvFinalRetrievalError,
    evaluate_retrieval_scenarios,
    load_retrieval_scenarios,
)
from cv_retrieval_test_helpers import (
    CandidateSpec,
    build_candidate_result,
    finalize_for_test,
)


class MappingFinalRetriever:
    def __init__(self, results):
        self.results = results

    def retrieve(self, query):
        value = self.results[query.text]
        if isinstance(value, Exception):
            raise value
        return value


def _write_plan(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "search_scenarios": [
                    {
                        "scenario_id": "supported",
                        "question": "Find Python and PostgreSQL candidates.",
                        "expected_candidate_ids": ["candidate_001"],
                        "required_evidence": ["Python", "PostgreSQL"],
                        "answer_behavior": "Return the supported candidate.",
                    },
                    {
                        "scenario_id": "unsupported",
                        "question": "Who holds government security clearance?",
                        "expected_candidate_ids": [],
                        "required_evidence": [],
                        "answer_behavior": "State that evidence is unavailable.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def test_load_retrieval_scenarios_validates_plan_content(tmp_path) -> None:
    plan = _write_plan(tmp_path / "plan.json")

    scenarios = load_retrieval_scenarios(plan)

    assert [scenario.scenario_id for scenario in scenarios] == [
        "supported",
        "unsupported",
    ]
    assert scenarios[0].expected_candidate_ids == ("candidate_001",)


def test_evaluation_requires_expected_ids_and_unsupported_empty_result(
    tmp_path,
) -> None:
    plan = _write_plan(tmp_path / "plan.json")
    supported = finalize_for_test(
        build_candidate_result(
            (
                CandidateSpec(
                    "candidate_001",
                    "Supported Candidate",
                    "Python Engineer",
                    matched_count=2,
                    candidate_score=0.9,
                    coverage_score=1.0,
                ),
            )
        )
    )
    unsupported = finalize_for_test(
        build_candidate_result(
            (
                CandidateSpec(
                    "candidate_noise",
                    "Noise Candidate",
                    "Platform Engineer",
                    matched_count=1,
                    candidate_score=0.2,
                    coverage_score=1 / 3,
                ),
            ),
            question="Who holds government security clearance?",
            condition_labels=("government", "security", "clearance"),
        )
    )
    retriever = MappingFinalRetriever(
        {
            "Find Python and PostgreSQL candidates.": supported,
            "Who holds government security clearance?": unsupported,
        }
    )

    report = evaluate_retrieval_scenarios(retriever, plan_path=plan)

    assert report.passed is True
    assert report.passed_count == 2
    assert all(item.source_traceable for item in report.evaluations)
    assert all(item.budget_compliant for item in report.evaluations)


def test_evaluation_reports_missing_expected_candidate_and_retrieval_error(
    tmp_path,
) -> None:
    plan = _write_plan(tmp_path / "plan.json")
    wrong = finalize_for_test(
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
        {
            "Find Python and PostgreSQL candidates.": wrong,
            "Who holds government security clearance?": CvFinalRetrievalError(
                "index unavailable"
            ),
        }
    )

    report = evaluate_retrieval_scenarios(retriever, plan_path=plan)

    assert report.passed is False
    assert report.failed_count == 2
    assert report.evaluations[0].missing_expected_candidate_ids == (
        "candidate_001",
    )
    assert report.evaluations[1].outcome == "error"
    assert report.evaluations[1].error == "index unavailable"


def test_evaluation_filters_scenarios_and_rejects_unknown_ids(tmp_path) -> None:
    plan = _write_plan(tmp_path / "plan.json")
    supported = finalize_for_test(
        build_candidate_result(
            (
                CandidateSpec(
                    "candidate_001",
                    "Supported Candidate",
                    "Python Engineer",
                    matched_count=2,
                    candidate_score=0.9,
                    coverage_score=1.0,
                ),
            )
        )
    )
    retriever = MappingFinalRetriever(
        {"Find Python and PostgreSQL candidates.": supported}
    )

    report = evaluate_retrieval_scenarios(
        retriever,
        plan_path=plan,
        scenario_ids=("supported",),
    )

    assert report.scenario_count == 1
    assert report.passed is True
    with pytest.raises(ValueError, match="Unknown retrieval scenario IDs"):
        evaluate_retrieval_scenarios(
            retriever,
            plan_path=plan,
            scenario_ids=("missing",),
        )
