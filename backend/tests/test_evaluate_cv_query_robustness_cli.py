"""CLI tests for the recruiter-query robustness diagnostic."""

import json
from types import SimpleNamespace

from app.scripts.evaluate_cv_query_robustness import run_cli
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


def _matrix(tmp_path):
    path = tmp_path / "matrix.json"
    path.write_text(
        json.dumps(
            {
                "matrix_version": 1,
                "description": "CLI test matrix.",
                "default_semantic_result_limit": 50,
                "default_candidate_limit": 5,
                "families": [
                    {
                        "family_id": "python",
                        "description": "Python paraphrases.",
                        "expected_outcome": "supported",
                        "candidate_policy": "exact",
                        "expected_candidate_ids": ["candidate_001"],
                        "minimum_returned_candidates": 1,
                        "questions": [
                            {
                                "scenario_id": "python_one",
                                "question": "Find Python candidates.",
                            },
                            {
                                "scenario_id": "python_two",
                                "question": "Who knows Python?",
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _result(question: str, candidate_id: str = "candidate_001"):
    return finalize_for_test(
        build_candidate_result(
            (
                CandidateSpec(
                    candidate_id,
                    "Candidate",
                    "Python Engineer",
                    matched_count=1,
                    candidate_score=0.9,
                    coverage_score=1.0,
                ),
            ),
            question=question,
            condition_labels=("python",),
        ),
        question=question,
        candidate_limit=5,
    )


def test_cli_prints_diagnostics_and_writes_json(tmp_path, capsys) -> None:
    matrix = _matrix(tmp_path)
    json_output = tmp_path / "reports" / "robustness.json"
    retriever = MappingFinalRetriever(
        {
            "Find Python candidates.": _result("Find Python candidates."),
            "Who knows Python?": _result("Who knows Python?"),
        }
    )

    status = run_cli(
        ["--verbose", "--json-output", str(json_output), "--strict"],
        settings=SimpleNamespace(
            cv_query_robustness_matrix_path=matrix,
        ),
        retriever=retriever,
    )
    output = capsys.readouterr().out
    payload = json.loads(json_output.read_text(encoding="utf-8"))

    assert status == 0
    assert "CV QUERY ROBUSTNESS DIAGNOSTIC" in output
    assert "Scenarios: 2" in output
    assert "Hosted provider calls made: 0" in output
    assert "parser.hard_conditions" in output
    assert payload["summary"]["passed"] is True
    assert payload["summary"]["hosted_provider_calls_made"] == 0


def test_cli_is_non_blocking_by_default_and_strict_on_mismatch(
    tmp_path,
    capsys,
) -> None:
    matrix = _matrix(tmp_path)
    retriever = MappingFinalRetriever(
        {
            "Find Python candidates.": _result(
                "Find Python candidates.",
                candidate_id="candidate_999",
            ),
            "Who knows Python?": _result(
                "Who knows Python?",
                candidate_id="candidate_999",
            ),
        }
    )
    settings = SimpleNamespace(cv_query_robustness_matrix_path=matrix)

    non_strict = run_cli([], settings=settings, retriever=retriever)
    first_output = capsys.readouterr().out
    strict = run_cli(
        ["--strict", "--failed-only"],
        settings=settings,
        retriever=retriever,
    )
    second_output = capsys.readouterr().out

    assert non_strict == 0
    assert "BASELINE MISMATCHES FOUND" in first_output
    assert strict == 1
    assert "candidate policy exact failed" in second_output
