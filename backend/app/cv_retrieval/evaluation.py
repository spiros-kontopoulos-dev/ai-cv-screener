"""End-to-end evaluation of final CV retrieval against committed scenarios."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Protocol

from app.cv_retrieval.final_retrieval import (
    CvFinalRetrievalError,
    FinalCvRetrievalQuery,
    FinalCvRetrievalResult,
)


@dataclass(frozen=True, slots=True)
class CvRetrievalScenario:
    """One committed recruiter question and its expected candidate identities."""

    scenario_id: str
    question: str
    expected_candidate_ids: tuple[str, ...]
    required_evidence: tuple[str, ...]
    answer_behavior: str

    def __post_init__(self) -> None:
        if not self.scenario_id.strip() or not self.question.strip():
            raise ValueError("Retrieval scenarios require ID and question.")
        if len(self.expected_candidate_ids) != len(
            set(self.expected_candidate_ids)
        ):
            raise ValueError("Expected candidate IDs must be unique.")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CvRetrievalScenario":
        return cls(
            scenario_id=_required_text(value, "scenario_id"),
            question=_required_text(value, "question"),
            expected_candidate_ids=tuple(
                _required_text_item(item, "expected_candidate_ids")
                for item in _required_list(value, "expected_candidate_ids")
            ),
            required_evidence=tuple(
                _required_text_item(item, "required_evidence")
                for item in _required_list(value, "required_evidence")
            ),
            answer_behavior=_required_text(value, "answer_behavior"),
        )


@dataclass(frozen=True, slots=True)
class CvRetrievalScenarioEvaluation:
    """Validation result for one end-to-end retrieval scenario."""

    scenario: CvRetrievalScenario
    passed: bool
    outcome: str
    returned_candidate_ids: tuple[str, ...]
    missing_expected_candidate_ids: tuple[str, ...]
    unexpected_candidate_ids: tuple[str, ...]
    source_traceable: bool
    budget_compliant: bool
    context_character_count: int
    evidence_chunk_count: int
    error: str | None = None

    def __post_init__(self) -> None:
        if self.context_character_count < 0 or self.evidence_chunk_count < 0:
            raise ValueError("Evaluation counts cannot be negative.")
        if self.passed and self.error is not None:
            raise ValueError("Passing evaluations cannot contain an error.")


@dataclass(frozen=True, slots=True)
class CvRetrievalEvaluationReport:
    """Aggregate result for the committed retrieval scenario suite."""

    plan_path: Path
    evaluations: tuple[CvRetrievalScenarioEvaluation, ...]

    @property
    def scenario_count(self) -> int:
        return len(self.evaluations)

    @property
    def passed_count(self) -> int:
        return sum(evaluation.passed for evaluation in self.evaluations)

    @property
    def failed_count(self) -> int:
        return self.scenario_count - self.passed_count

    @property
    def passed(self) -> bool:
        return self.scenario_count > 0 and self.failed_count == 0


class FinalRetrieverProtocol(Protocol):
    def retrieve(self, query: FinalCvRetrievalQuery) -> FinalCvRetrievalResult:
        """Return final source-traceable evidence for one question."""


def load_retrieval_scenarios(plan_path: Path) -> tuple[CvRetrievalScenario, ...]:
    """Load and validate committed scenarios from the dataset plan."""

    try:
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"Could not read retrieval scenario plan {plan_path}: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise ValueError("Candidate dataset plan must contain a JSON object.")
    raw_scenarios = payload.get("search_scenarios")
    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        raise ValueError("Candidate dataset plan has no search scenarios.")
    scenarios = tuple(
        CvRetrievalScenario.from_mapping(value)
        for value in raw_scenarios
        if isinstance(value, dict)
    )
    if len(scenarios) != len(raw_scenarios):
        raise ValueError("Every search scenario must be a JSON object.")
    identifiers = [scenario.scenario_id for scenario in scenarios]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Search scenario IDs must be unique.")
    return scenarios


def evaluate_retrieval_scenarios(
    retriever: FinalRetrieverProtocol,
    *,
    plan_path: Path,
    scenario_ids: tuple[str, ...] = (),
    semantic_result_limit: int | None = None,
    candidate_limit: int | None = None,
) -> CvRetrievalEvaluationReport:
    """Run final retrieval and validate expected IDs, sources, and budgets."""

    scenarios = load_retrieval_scenarios(plan_path)
    if scenario_ids:
        requested = set(scenario_ids)
        known = {scenario.scenario_id for scenario in scenarios}
        unknown = requested - known
        if unknown:
            raise ValueError(
                "Unknown retrieval scenario IDs: " + ", ".join(sorted(unknown))
            )
        scenarios = tuple(
            scenario
            for scenario in scenarios
            if scenario.scenario_id in requested
        )

    evaluations = tuple(
        _evaluate_one_scenario(
            retriever,
            scenario,
            semantic_result_limit=semantic_result_limit,
            candidate_limit=candidate_limit,
        )
        for scenario in scenarios
    )
    return CvRetrievalEvaluationReport(
        plan_path=plan_path,
        evaluations=evaluations,
    )


def _evaluate_one_scenario(
    retriever: FinalRetrieverProtocol,
    scenario: CvRetrievalScenario,
    *,
    semantic_result_limit: int | None,
    candidate_limit: int | None,
) -> CvRetrievalScenarioEvaluation:
    try:
        result = retriever.retrieve(
            FinalCvRetrievalQuery(
                scenario.question,
                semantic_result_limit=semantic_result_limit,
                candidate_limit=candidate_limit,
            )
        )
    except (CvFinalRetrievalError, ValueError) as error:
        return CvRetrievalScenarioEvaluation(
            scenario=scenario,
            passed=False,
            outcome="error",
            returned_candidate_ids=(),
            missing_expected_candidate_ids=scenario.expected_candidate_ids,
            unexpected_candidate_ids=(),
            source_traceable=False,
            budget_compliant=False,
            context_character_count=0,
            evidence_chunk_count=0,
            error=str(error),
        )

    returned_ids = tuple(candidate.candidate_id for candidate in result.candidates)
    expected = set(scenario.expected_candidate_ids)
    returned = set(returned_ids)
    missing = tuple(
        candidate_id
        for candidate_id in scenario.expected_candidate_ids
        if candidate_id not in returned
    )
    unexpected = tuple(
        candidate_id for candidate_id in returned_ids if candidate_id not in expected
    )
    source_traceable = _is_source_traceable(result)
    budget_compliant = (
        result.context_character_count <= result.max_context_characters
        and result.evidence_chunk_count <= result.max_total_evidence_chunks
    )

    if expected:
        behavior_passed = result.outcome != "unsupported" and not missing
    else:
        behavior_passed = result.outcome == "unsupported" and not returned_ids
    passed = behavior_passed and source_traceable and budget_compliant
    return CvRetrievalScenarioEvaluation(
        scenario=scenario,
        passed=passed,
        outcome=result.outcome,
        returned_candidate_ids=returned_ids,
        missing_expected_candidate_ids=missing,
        unexpected_candidate_ids=unexpected,
        source_traceable=source_traceable,
        budget_compliant=budget_compliant,
        context_character_count=result.context_character_count,
        evidence_chunk_count=result.evidence_chunk_count,
    )


def _is_source_traceable(result: FinalCvRetrievalResult) -> bool:
    for candidate in result.candidates:
        if not candidate.evidence:
            return False
        for evidence in candidate.evidence:
            source = evidence.source
            if source.candidate_id != candidate.candidate_id:
                return False
            if not (
                source.document_id
                and source.document_hash
                and source.source_filename
                and source.section_name
                and source.page_numbers
                and evidence.chunk_id
            ):
                return False
            if evidence.chunk_id not in result.context_text:
                return False
            if source.source_filename not in result.context_text:
                return False
    return True


def _required_text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"Retrieval scenario field '{key}' must be text.")
    return item.strip()


def _required_list(value: Mapping[str, Any], key: str) -> list[Any]:
    item = value.get(key)
    if not isinstance(item, list):
        raise ValueError(f"Retrieval scenario field '{key}' must be a list.")
    return item


def _required_text_item(item: Any, key: str) -> str:
    if not isinstance(item, str) or not item.strip():
        raise ValueError(
            f"Retrieval scenario list '{key}' must contain non-empty text."
        )
    return item.strip()
