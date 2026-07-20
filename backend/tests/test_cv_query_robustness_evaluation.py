"""Tests for the diagnostic recruiter-query robustness matrix."""

import json
from pathlib import Path

import pytest

from app.cv_retrieval import (
    CvFinalRetrievalError,
    evaluate_query_robustness,
    load_query_robustness_matrix,
)
from cv_retrieval_test_helpers import (
    CandidateSpec,
    build_candidate_result,
    finalize_for_test,
)


class MappingFinalRetriever:
    def __init__(self, results):
        self.results = results
        self.queries = []

    def retrieve(self, query):
        self.queries.append(query)
        value = self.results[query.text]
        if isinstance(value, Exception):
            raise value
        return value


def _write_matrix(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "matrix_version": 1,
                "description": "Small deterministic test matrix.",
                "default_semantic_result_limit": 77,
                "default_candidate_limit": 6,
                "families": [
                    {
                        "family_id": "exact_stack",
                        "description": "Equivalent stack questions.",
                        "expected_outcome": "supported",
                        "candidate_policy": "exact",
                        "expected_candidate_ids": [
                            "candidate_001",
                            "candidate_002",
                        ],
                        "minimum_returned_candidates": 2,
                        "questions": [
                            {
                                "scenario_id": "stack_one",
                                "question": "Find Python candidates.",
                            },
                            {
                                "scenario_id": "stack_two",
                                "question": "Who knows Python?",
                            },
                        ],
                    },
                    {
                        "family_id": "unsupported",
                        "description": "Unsupported controls.",
                        "expected_outcome": "unsupported",
                        "candidate_policy": "none",
                        "expected_candidate_ids": [],
                        "minimum_returned_candidates": 0,
                        "questions": [
                            {
                                "scenario_id": "none_one",
                                "question": "Who has security clearance?",
                            },
                            {
                                "scenario_id": "none_two",
                                "question": "Who can access classified data?",
                            },
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _supported(question: str):
    return finalize_for_test(
        build_candidate_result(
            (
                CandidateSpec(
                    "candidate_001",
                    "First Candidate",
                    "Python Engineer",
                    matched_count=1,
                    candidate_score=0.9,
                    coverage_score=1.0,
                ),
                CandidateSpec(
                    "candidate_002",
                    "Second Candidate",
                    "Python Engineer",
                    matched_count=1,
                    candidate_score=0.85,
                    coverage_score=1.0,
                ),
            ),
            question=question,
            condition_labels=("python",),
        ),
        question=question,
        candidate_limit=6,
    )


def _unsupported(question: str):
    return finalize_for_test(
        build_candidate_result(
            (
                CandidateSpec(
                    "candidate_noise",
                    "Noise Candidate",
                    "Platform Engineer",
                    matched_count=0,
                    candidate_score=0.1,
                    coverage_score=0.0,
                ),
            ),
            question=question,
            condition_labels=("clearance",),
        ),
        question=question,
        candidate_limit=6,
    )


def test_committed_matrix_covers_twelve_families_and_forty_eight_questions(
) -> None:
    matrix_path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "dataset"
        / "cv_query_robustness_matrix.json"
    )
    matrix = load_query_robustness_matrix(matrix_path)

    assert len(matrix.families) == 13
    assert matrix.scenario_count == 50
    scenario_ids = {
        question.scenario_id
        for family in matrix.families
        for question in family.questions
    }
    assert {
        "engineering_knows",
        "bsc_full_phrase",
        "experience_more_than",
        "clearance_canonical",
    }.issubset(scenario_ids)


def test_matrix_loader_rejects_duplicate_scenario_ids(tmp_path) -> None:
    matrix_path = _write_matrix(tmp_path / "matrix.json")
    payload = json.loads(matrix_path.read_text(encoding="utf-8"))
    payload["families"][1]["questions"][0]["scenario_id"] = "stack_one"
    matrix_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="scenario IDs must be globally unique"):
        load_query_robustness_matrix(matrix_path)


def test_evaluator_records_parser_candidate_and_provider_diagnostics(
    tmp_path,
) -> None:
    matrix_path = _write_matrix(tmp_path / "matrix.json")
    retriever = MappingFinalRetriever(
        {
            "Find Python candidates.": _supported(
                "Find Python candidates."
            ),
            "Who knows Python?": _supported("Who knows Python?"),
            "Who has security clearance?": _unsupported(
                "Who has security clearance?"
            ),
            "Who can access classified data?": _unsupported(
                "Who can access classified data?"
            ),
        }
    )

    report = evaluate_query_robustness(
        retriever,
        matrix_path=matrix_path,
    )

    assert report.passed is True
    assert report.scenario_count == 4
    assert report.hosted_provider_calls_made == 0
    assert all(
        query.semantic_result_limit == 77
        and query.candidate_limit == 6
        for query in retriever.queries
    )
    supported = report.family_evaluations[0].evaluations[1]
    assert supported.hosted_provider_would_be_called is True
    assert supported.parser is not None
    assert supported.parser.lexical_terms == ("python",)
    assert "knows" in supported.parser.discarded_tokens
    assert supported.parser.hard_conditions
    assert supported.candidate_diagnostics[0].selected_for_final_context is True
    unsupported = report.family_evaluations[1].evaluations[0]
    assert unsupported.hosted_provider_would_be_called is False
    assert unsupported.returned_candidate_ids == ()


def test_subset_policy_allows_only_qualifying_candidates(tmp_path) -> None:
    matrix_path = _write_matrix(tmp_path / "matrix.json")
    payload = json.loads(matrix_path.read_text(encoding="utf-8"))
    family = payload["families"][0]
    family["candidate_policy"] = "subset"
    family["minimum_returned_candidates"] = 1
    family["expected_candidate_ids"] = [
        "candidate_001",
        "candidate_002",
        "candidate_003",
    ]
    family["questions"] = family["questions"][:2]
    payload["families"] = [family]
    matrix_path.write_text(json.dumps(payload), encoding="utf-8")
    one_candidate = finalize_for_test(
        build_candidate_result(
            (
                CandidateSpec(
                    "candidate_001",
                    "First Candidate",
                    "Python Engineer",
                    matched_count=1,
                    candidate_score=0.9,
                    coverage_score=1.0,
                ),
            ),
            question="Find Python candidates.",
            condition_labels=("python",),
        ),
        question="Find Python candidates.",
        candidate_limit=6,
    )
    retriever = MappingFinalRetriever(
        {
            "Find Python candidates.": one_candidate,
            "Who knows Python?": finalize_for_test(
                build_candidate_result(
                    (
                        CandidateSpec(
                            "candidate_noise",
                            "Noise Candidate",
                            "Designer",
                            matched_count=1,
                            candidate_score=0.9,
                            coverage_score=1.0,
                        ),
                    ),
                    question="Who knows Python?",
                    condition_labels=("python",),
                ),
                question="Who knows Python?",
                candidate_limit=6,
            ),
        }
    )

    report = evaluate_query_robustness(
        retriever,
        matrix_path=matrix_path,
    )

    assert report.passed is False
    evaluations = report.family_evaluations[0].evaluations
    assert evaluations[0].passed is True
    assert evaluations[1].passed is False
    assert evaluations[1].unexpected_candidate_ids == ("candidate_noise",)
    assert "candidate policy subset failed" in evaluations[1].failure_reasons[0]


def test_evaluator_captures_retrieval_errors_and_filters(tmp_path) -> None:
    matrix_path = _write_matrix(tmp_path / "matrix.json")
    retriever = MappingFinalRetriever(
        {
            "Who knows Python?": CvFinalRetrievalError("index unavailable"),
        }
    )

    report = evaluate_query_robustness(
        retriever,
        matrix_path=matrix_path,
        scenario_ids=("stack_two",),
    )

    assert report.scenario_count == 1
    assert report.failed_count == 1
    evaluation = report.family_evaluations[0].evaluations[0]
    assert evaluation.outcome == "error"
    assert evaluation.error == "index unavailable"
    assert evaluation.parser is None

    with pytest.raises(ValueError, match="Unknown robustness family IDs"):
        evaluate_query_robustness(
            retriever,
            matrix_path=matrix_path,
            family_ids=("missing",),
        )


def test_report_json_contains_summary_and_full_diagnostics(tmp_path) -> None:
    matrix_path = _write_matrix(tmp_path / "matrix.json")
    retriever = MappingFinalRetriever(
        {
            "Find Python candidates.": _supported(
                "Find Python candidates."
            ),
            "Who knows Python?": _supported("Who knows Python?"),
        }
    )

    report = evaluate_query_robustness(
        retriever,
        matrix_path=matrix_path,
        family_ids=("exact_stack",),
    )
    payload = report.to_json_dict()

    assert payload["matrix_path"] == str(matrix_path)
    assert payload["summary"]["scenario_count"] == 2
    assert payload["summary"]["hosted_provider_calls_made"] == 0
    first = payload["family_evaluations"][0]["evaluations"][0]
    assert first["parser"]["hard_conditions"]
    assert first["candidate_diagnostics"]
