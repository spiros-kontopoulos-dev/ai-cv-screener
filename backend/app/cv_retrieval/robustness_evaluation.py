"""Diagnostic evaluation for recruiter-query paraphrase robustness.

This module deliberately does not change retrieval behavior. It runs the
existing final retriever against a controlled matrix and records where a
question was lost: query features, hard candidate conditions, candidate-level
coverage, support thresholds, or final source budgeting.

The matrix belongs to the committed synthetic corpus and acts only as an
evaluation oracle. The rendered PDFs and their persisted chunks remain the
application evidence boundary.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol

from app.cv_retrieval.candidate_ranking import CandidateQueryCondition
from app.cv_retrieval.evidence_analysis import (
    CvQueryEvidenceFeatures,
    canonicalize_lexical_term,
)
from app.cv_retrieval.final_retrieval import (
    CvFinalRetrievalError,
    FinalCvRetrievalQuery,
    FinalCvRetrievalResult,
)


CandidatePolicy = Literal[
    "exact",
    "contains_all",
    "subset",
    "any_of",
    "none",
]
ExpectedOutcome = Literal["supported", "partial", "unsupported"]

_NUMBER_WORDS = {
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
    "hundred",
}


@dataclass(frozen=True, slots=True)
class CvQueryRobustnessQuestion:
    """One natural-language formulation inside an equivalence family."""

    scenario_id: str
    question: str

    def __post_init__(self) -> None:
        if not self.scenario_id.strip() or not self.question.strip():
            raise ValueError("Robustness questions require ID and text.")

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Any],
    ) -> "CvQueryRobustnessQuestion":
        return cls(
            scenario_id=_required_text(value, "scenario_id"),
            question=_required_text(value, "question"),
        )


@dataclass(frozen=True, slots=True)
class CvQueryRobustnessFamily:
    """Equivalent questions plus one candidate/outcome expectation."""

    family_id: str
    description: str
    expected_outcome: ExpectedOutcome
    candidate_policy: CandidatePolicy
    expected_candidate_ids: tuple[str, ...]
    minimum_returned_candidates: int
    questions: tuple[CvQueryRobustnessQuestion, ...]

    def __post_init__(self) -> None:
        if not self.family_id.strip() or not self.description.strip():
            raise ValueError("Robustness families require ID and description.")
        if self.expected_outcome not in {
            "supported",
            "partial",
            "unsupported",
        }:
            raise ValueError(
                f"Unsupported expected outcome: {self.expected_outcome}."
            )
        if self.candidate_policy not in {
            "exact",
            "contains_all",
            "subset",
            "any_of",
            "none",
        }:
            raise ValueError(
                f"Unsupported candidate policy: {self.candidate_policy}."
            )
        if self.minimum_returned_candidates < 0:
            raise ValueError("Minimum returned candidates cannot be negative.")
        if len(self.expected_candidate_ids) != len(
            set(self.expected_candidate_ids)
        ):
            raise ValueError("Expected candidate IDs must be unique per family.")
        if not self.questions:
            raise ValueError("Robustness families require questions.")
        if self.candidate_policy == "none":
            if self.expected_candidate_ids:
                raise ValueError(
                    "The none policy cannot declare expected candidates."
                )
            if self.minimum_returned_candidates != 0:
                raise ValueError(
                    "The none policy requires a zero minimum candidate count."
                )
            if self.expected_outcome != "unsupported":
                raise ValueError(
                    "The none policy must expect an unsupported outcome."
                )
        elif not self.expected_candidate_ids:
            raise ValueError(
                "Candidate policies other than none require expected IDs."
            )
        if (
            self.candidate_policy in {"exact", "contains_all"}
            and self.minimum_returned_candidates
            > len(self.expected_candidate_ids)
        ):
            raise ValueError(
                "Minimum candidate count exceeds the exact expectation set."
            )

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Any],
    ) -> "CvQueryRobustnessFamily":
        questions = tuple(
            CvQueryRobustnessQuestion.from_mapping(item)
            for item in _required_mapping_list(value, "questions")
        )
        return cls(
            family_id=_required_text(value, "family_id"),
            description=_required_text(value, "description"),
            expected_outcome=_required_text(  # type: ignore[arg-type]
                value,
                "expected_outcome",
            ),
            candidate_policy=_required_text(  # type: ignore[arg-type]
                value,
                "candidate_policy",
            ),
            expected_candidate_ids=tuple(
                _required_text_item(item, "expected_candidate_ids")
                for item in _required_list(value, "expected_candidate_ids")
            ),
            minimum_returned_candidates=_required_non_negative_integer(
                value,
                "minimum_returned_candidates",
            ),
            questions=questions,
        )


@dataclass(frozen=True, slots=True)
class CvQueryRobustnessMatrix:
    """Complete committed diagnostic matrix and default retrieval controls."""

    matrix_version: int
    description: str
    default_semantic_result_limit: int
    default_candidate_limit: int
    families: tuple[CvQueryRobustnessFamily, ...]

    def __post_init__(self) -> None:
        if self.matrix_version < 1:
            raise ValueError("Robustness matrix version must be positive.")
        if not self.description.strip():
            raise ValueError("Robustness matrix description is required.")
        if self.default_semantic_result_limit < 1:
            raise ValueError("Default semantic result limit must be positive.")
        if self.default_candidate_limit < 1:
            raise ValueError("Default candidate limit must be positive.")
        if not self.families:
            raise ValueError("Robustness matrix must contain families.")
        if any(len(family.questions) < 2 for family in self.families):
            raise ValueError(
                "Every robustness family must contain at least two paraphrases."
            )

        family_ids = [family.family_id for family in self.families]
        if len(family_ids) != len(set(family_ids)):
            raise ValueError("Robustness family IDs must be unique.")
        scenario_ids = [
            question.scenario_id
            for family in self.families
            for question in family.questions
        ]
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("Robustness scenario IDs must be globally unique.")

    @property
    def scenario_count(self) -> int:
        return sum(len(family.questions) for family in self.families)


@dataclass(frozen=True, slots=True)
class CvQueryConditionDiagnostic:
    """Serializable representation of one current hard query condition."""

    key: str
    label: str
    kind: str
    weight: float
    terms: tuple[str, ...]
    alternatives: tuple[str, ...]
    numeric_value: str | None


@dataclass(frozen=True, slots=True)
class CvQueryParserDiagnostic:
    """Transparent snapshot of query features and candidate conditions."""

    normalized_text: str
    lexical_terms: tuple[str, ...]
    lexical_phrases: tuple[str, ...]
    text_relations: tuple[str, ...]
    education_constraints: tuple[str, ...]
    numeric_constraints: tuple[str, ...]
    hard_conditions: tuple[CvQueryConditionDiagnostic, ...]
    unconditioned_lexical_terms: tuple[str, ...]
    discarded_tokens: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CvCandidateCoverageDiagnostic:
    """Candidate-level coverage before final support thresholds are applied."""

    rank: int
    candidate_id: str
    candidate_name: str | None
    professional_title: str | None
    candidate_score: float
    coverage_score: float
    matched_condition_labels: tuple[str, ...]
    missing_condition_labels: tuple[str, ...]
    selected_for_final_context: bool


@dataclass(frozen=True, slots=True)
class CvQueryRobustnessScenarioEvaluation:
    """Diagnostic result for one paraphrase without calling an answer model."""

    family_id: str
    scenario_id: str
    question: str
    expected_outcome: str
    candidate_policy: str
    expected_candidate_ids: tuple[str, ...]
    minimum_returned_candidates: int
    passed: bool
    outcome: str
    returned_candidate_ids: tuple[str, ...]
    missing_expected_candidate_ids: tuple[str, ...]
    unexpected_candidate_ids: tuple[str, ...]
    source_traceable: bool
    budget_compliant: bool
    hosted_provider_would_be_called: bool
    parser: CvQueryParserDiagnostic | None
    candidate_diagnostics: tuple[CvCandidateCoverageDiagnostic, ...]
    failure_reasons: tuple[str, ...]
    error: str | None = None

    def __post_init__(self) -> None:
        if self.passed and (self.failure_reasons or self.error):
            raise ValueError(
                "Passing robustness scenarios cannot contain failures."
            )


@dataclass(frozen=True, slots=True)
class CvQueryRobustnessFamilyEvaluation:
    """Aggregate paraphrase-consistency diagnostics for one family."""

    family: CvQueryRobustnessFamily
    evaluations: tuple[CvQueryRobustnessScenarioEvaluation, ...]

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

    @property
    def outcome_consistent(self) -> bool:
        return len({evaluation.outcome for evaluation in self.evaluations}) == 1

    @property
    def candidate_set_consistent(self) -> bool:
        signatures = {
            frozenset(evaluation.returned_candidate_ids)
            for evaluation in self.evaluations
        }
        return len(signatures) == 1


@dataclass(frozen=True, slots=True)
class CvQueryRobustnessReport:
    """Full diagnostic report for selected matrix families and scenarios."""

    matrix_path: Path
    matrix_version: int
    semantic_result_limit: int
    candidate_limit: int
    family_evaluations: tuple[CvQueryRobustnessFamilyEvaluation, ...]

    @property
    def family_count(self) -> int:
        return len(self.family_evaluations)

    @property
    def scenario_count(self) -> int:
        return sum(
            family.scenario_count for family in self.family_evaluations
        )

    @property
    def passed_count(self) -> int:
        return sum(family.passed_count for family in self.family_evaluations)

    @property
    def failed_count(self) -> int:
        return self.scenario_count - self.passed_count

    @property
    def passed(self) -> bool:
        return self.scenario_count > 0 and self.failed_count == 0

    @property
    def inconsistent_outcome_family_count(self) -> int:
        return sum(
            not family.outcome_consistent
            for family in self.family_evaluations
        )

    @property
    def inconsistent_candidate_family_count(self) -> int:
        return sum(
            not family.candidate_set_consistent
            for family in self.family_evaluations
        )

    @property
    def hosted_provider_calls_made(self) -> int:
        """The diagnostic evaluator never calls OpenAI or Gemini."""

        return 0

    def to_json_dict(self) -> dict[str, Any]:
        """Return a stable JSON-serializable report for later comparisons."""

        payload = asdict(self)
        payload["matrix_path"] = str(self.matrix_path)
        payload["summary"] = {
            "family_count": self.family_count,
            "scenario_count": self.scenario_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "passed": self.passed,
            "inconsistent_outcome_family_count": (
                self.inconsistent_outcome_family_count
            ),
            "inconsistent_candidate_family_count": (
                self.inconsistent_candidate_family_count
            ),
            "hosted_provider_calls_made": self.hosted_provider_calls_made,
        }
        return payload


class FinalRetrieverProtocol(Protocol):
    """Small boundary used by production retrieval and deterministic tests."""

    def retrieve(self, query: FinalCvRetrievalQuery) -> FinalCvRetrievalResult:
        """Return final source-traceable evidence for one question."""


def load_query_robustness_matrix(path: Path) -> CvQueryRobustnessMatrix:
    """Load and validate the committed paraphrase-equivalence matrix."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"Could not read query robustness matrix {path}: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise ValueError("Query robustness matrix must contain a JSON object.")

    families = tuple(
        CvQueryRobustnessFamily.from_mapping(item)
        for item in _required_mapping_list(payload, "families")
    )
    return CvQueryRobustnessMatrix(
        matrix_version=_required_positive_integer(payload, "matrix_version"),
        description=_required_text(payload, "description"),
        default_semantic_result_limit=_required_positive_integer(
            payload,
            "default_semantic_result_limit",
        ),
        default_candidate_limit=_required_positive_integer(
            payload,
            "default_candidate_limit",
        ),
        families=families,
    )


def evaluate_query_robustness(
    retriever: FinalRetrieverProtocol,
    *,
    matrix_path: Path,
    family_ids: tuple[str, ...] = (),
    scenario_ids: tuple[str, ...] = (),
    semantic_result_limit: int | None = None,
    candidate_limit: int | None = None,
    diagnostic_candidate_limit: int = 5,
) -> CvQueryRobustnessReport:
    """Evaluate selected paraphrases through the unchanged final retriever."""

    if diagnostic_candidate_limit < 1:
        raise ValueError("Diagnostic candidate limit must be positive.")

    matrix = load_query_robustness_matrix(matrix_path)
    selected_families = _select_families(
        matrix,
        family_ids=family_ids,
        scenario_ids=scenario_ids,
    )
    resolved_semantic_limit = (
        matrix.default_semantic_result_limit
        if semantic_result_limit is None
        else semantic_result_limit
    )
    resolved_candidate_limit = (
        matrix.default_candidate_limit
        if candidate_limit is None
        else candidate_limit
    )
    if resolved_semantic_limit < 1 or resolved_candidate_limit < 1:
        raise ValueError("Retrieval limits must be positive.")

    family_evaluations = tuple(
        CvQueryRobustnessFamilyEvaluation(
            family=family,
            evaluations=tuple(
                _evaluate_question(
                    retriever,
                    family=family,
                    question=question,
                    semantic_result_limit=resolved_semantic_limit,
                    candidate_limit=resolved_candidate_limit,
                    diagnostic_candidate_limit=diagnostic_candidate_limit,
                )
                for question in family.questions
            ),
        )
        for family in selected_families
    )
    return CvQueryRobustnessReport(
        matrix_path=matrix_path,
        matrix_version=matrix.matrix_version,
        semantic_result_limit=resolved_semantic_limit,
        candidate_limit=resolved_candidate_limit,
        family_evaluations=family_evaluations,
    )


def _select_families(
    matrix: CvQueryRobustnessMatrix,
    *,
    family_ids: tuple[str, ...],
    scenario_ids: tuple[str, ...],
) -> tuple[CvQueryRobustnessFamily, ...]:
    known_family_ids = {family.family_id for family in matrix.families}
    unknown_families = set(family_ids) - known_family_ids
    if unknown_families:
        raise ValueError(
            "Unknown robustness family IDs: "
            + ", ".join(sorted(unknown_families))
        )

    known_scenario_ids = {
        question.scenario_id
        for family in matrix.families
        for question in family.questions
    }
    unknown_scenarios = set(scenario_ids) - known_scenario_ids
    if unknown_scenarios:
        raise ValueError(
            "Unknown robustness scenario IDs: "
            + ", ".join(sorted(unknown_scenarios))
        )

    requested_families = set(family_ids)
    requested_scenarios = set(scenario_ids)
    selected: list[CvQueryRobustnessFamily] = []
    for family in matrix.families:
        if requested_families and family.family_id not in requested_families:
            continue
        questions = family.questions
        if requested_scenarios:
            questions = tuple(
                question
                for question in questions
                if question.scenario_id in requested_scenarios
            )
        if not questions:
            continue
        selected.append(
            CvQueryRobustnessFamily(
                family_id=family.family_id,
                description=family.description,
                expected_outcome=family.expected_outcome,
                candidate_policy=family.candidate_policy,
                expected_candidate_ids=family.expected_candidate_ids,
                minimum_returned_candidates=(
                    min(
                        family.minimum_returned_candidates,
                        len(family.expected_candidate_ids),
                    )
                    if family.candidate_policy != "none"
                    else 0
                ),
                questions=questions,
            )
        )

    if not selected:
        raise ValueError("No robustness scenarios matched the requested filters.")
    return tuple(selected)


def _evaluate_question(
    retriever: FinalRetrieverProtocol,
    *,
    family: CvQueryRobustnessFamily,
    question: CvQueryRobustnessQuestion,
    semantic_result_limit: int,
    candidate_limit: int,
    diagnostic_candidate_limit: int,
) -> CvQueryRobustnessScenarioEvaluation:
    try:
        result = retriever.retrieve(
            FinalCvRetrievalQuery(
                question.question,
                semantic_result_limit=semantic_result_limit,
                candidate_limit=candidate_limit,
            )
        )
    except (CvFinalRetrievalError, ValueError) as error:
        return CvQueryRobustnessScenarioEvaluation(
            family_id=family.family_id,
            scenario_id=question.scenario_id,
            question=question.question,
            expected_outcome=family.expected_outcome,
            candidate_policy=family.candidate_policy,
            expected_candidate_ids=family.expected_candidate_ids,
            minimum_returned_candidates=family.minimum_returned_candidates,
            passed=False,
            outcome="error",
            returned_candidate_ids=(),
            missing_expected_candidate_ids=family.expected_candidate_ids,
            unexpected_candidate_ids=(),
            source_traceable=False,
            budget_compliant=False,
            hosted_provider_would_be_called=False,
            parser=None,
            candidate_diagnostics=(),
            failure_reasons=("retrieval raised an error",),
            error=str(error),
        )

    returned_ids = tuple(candidate.candidate_id for candidate in result.candidates)
    expected_ids = set(family.expected_candidate_ids)
    returned_set = set(returned_ids)
    missing, unexpected, candidate_passed = _candidate_expectation(
        policy=family.candidate_policy,
        expected_ids=family.expected_candidate_ids,
        returned_ids=returned_ids,
        minimum_returned_candidates=family.minimum_returned_candidates,
    )
    source_traceable = _is_source_traceable(result)
    budget_compliant = (
        result.context_character_count <= result.max_context_characters
        and result.evidence_chunk_count <= result.max_total_evidence_chunks
    )

    failure_reasons: list[str] = []
    if result.outcome != family.expected_outcome:
        failure_reasons.append(
            f"expected outcome {family.expected_outcome}, got {result.outcome}"
        )
    if not candidate_passed:
        failure_reasons.append(
            _candidate_policy_failure(
                family.candidate_policy,
                expected_ids=expected_ids,
                returned_ids=returned_set,
                minimum_returned_candidates=family.minimum_returned_candidates,
            )
        )
    if not source_traceable:
        failure_reasons.append("returned evidence is not fully source traceable")
    if not budget_compliant:
        failure_reasons.append("final context exceeded a configured budget")

    parser = _build_parser_diagnostic(result)
    candidate_diagnostics = _build_candidate_diagnostics(
        result,
        limit=diagnostic_candidate_limit,
    )
    return CvQueryRobustnessScenarioEvaluation(
        family_id=family.family_id,
        scenario_id=question.scenario_id,
        question=question.question,
        expected_outcome=family.expected_outcome,
        candidate_policy=family.candidate_policy,
        expected_candidate_ids=family.expected_candidate_ids,
        minimum_returned_candidates=family.minimum_returned_candidates,
        passed=not failure_reasons,
        outcome=result.outcome,
        returned_candidate_ids=returned_ids,
        missing_expected_candidate_ids=missing,
        unexpected_candidate_ids=unexpected,
        source_traceable=source_traceable,
        budget_compliant=budget_compliant,
        hosted_provider_would_be_called=result.outcome != "unsupported",
        parser=parser,
        candidate_diagnostics=candidate_diagnostics,
        failure_reasons=tuple(failure_reasons),
    )


def _candidate_expectation(
    *,
    policy: CandidatePolicy,
    expected_ids: tuple[str, ...],
    returned_ids: tuple[str, ...],
    minimum_returned_candidates: int,
) -> tuple[tuple[str, ...], tuple[str, ...], bool]:
    expected = set(expected_ids)
    returned = set(returned_ids)
    missing = tuple(
        candidate_id
        for candidate_id in expected_ids
        if candidate_id not in returned
    )
    unexpected = tuple(
        candidate_id
        for candidate_id in returned_ids
        if candidate_id not in expected
    )
    count_passed = len(returned_ids) >= minimum_returned_candidates

    if policy == "exact":
        return missing, unexpected, count_passed and returned == expected
    if policy == "contains_all":
        return missing, (), count_passed and expected.issubset(returned)
    if policy == "subset":
        passed = (
            count_passed
            and bool(returned)
            and returned.issubset(expected)
        )
        return (), unexpected, passed
    if policy == "any_of":
        return (), (), count_passed and bool(returned & expected)
    if policy == "none":
        return (), unexpected, not returned
    raise ValueError(f"Unsupported candidate policy: {policy}.")


def _candidate_policy_failure(
    policy: CandidatePolicy,
    *,
    expected_ids: set[str],
    returned_ids: set[str],
    minimum_returned_candidates: int,
) -> str:
    return (
        f"candidate policy {policy} failed: expected={sorted(expected_ids)}, "
        f"returned={sorted(returned_ids)}, "
        f"minimum={minimum_returned_candidates}"
    )


def _build_parser_diagnostic(
    result: FinalCvRetrievalResult,
) -> CvQueryParserDiagnostic:
    candidate_result = result.candidate_result
    features = candidate_result.assisted_result.query_features
    conditions = candidate_result.conditions
    conditioned_terms = {
        term
        for condition in conditions
        for term in condition.terms
    }
    unconditioned = tuple(
        term for term in features.lexical_terms if term not in conditioned_terms
    )
    return CvQueryParserDiagnostic(
        normalized_text=features.normalized_text,
        lexical_terms=features.lexical_terms,
        lexical_phrases=features.lexical_phrases,
        text_relations=tuple(
            f"{relation.relation}:{'+'.join(relation.terms)}"
            for relation in features.text_relations
        ),
        education_constraints=tuple(
            constraint.display_label
            for constraint in features.education_constraints
        ),
        numeric_constraints=tuple(
            (
                f"{constraint.relation}:{constraint.operator}:"
                f"{constraint.display_value}"
            )
            for constraint in features.numeric_constraints
        ),
        hard_conditions=tuple(
            _condition_diagnostic(condition) for condition in conditions
        ),
        unconditioned_lexical_terms=unconditioned,
        discarded_tokens=_discarded_tokens(features),
    )


def _condition_diagnostic(
    condition: CandidateQueryCondition,
) -> CvQueryConditionDiagnostic:
    return CvQueryConditionDiagnostic(
        key=condition.key,
        label=condition.label,
        kind=condition.kind,
        weight=condition.weight,
        terms=condition.terms,
        alternatives=condition.alternatives,
        numeric_value=condition.numeric_value,
    )


def _discarded_tokens(
    features: CvQueryEvidenceFeatures,
) -> tuple[str, ...]:
    lexical = set(features.lexical_terms)
    discarded: list[str] = []
    for token in features.normalized_text.split():
        canonical = canonicalize_lexical_term(token)
        if not canonical or canonical in lexical:
            continue
        if token.isdigit() or token in _NUMBER_WORDS:
            continue
        if token not in discarded:
            discarded.append(token)
    return tuple(discarded)


def _build_candidate_diagnostics(
    result: FinalCvRetrievalResult,
    *,
    limit: int,
) -> tuple[CvCandidateCoverageDiagnostic, ...]:
    conditions = result.candidate_result.conditions
    all_labels = tuple(condition.label for condition in conditions)
    final_ids = {candidate.candidate_id for candidate in result.candidates}
    diagnostics: list[CvCandidateCoverageDiagnostic] = []
    for candidate in result.candidate_result.candidates[:limit]:
        matched_labels = tuple(
            match.condition.label for match in candidate.matched_conditions
        )
        matched_set = set(matched_labels)
        diagnostics.append(
            CvCandidateCoverageDiagnostic(
                rank=candidate.rank,
                candidate_id=candidate.candidate_id,
                candidate_name=candidate.candidate_name,
                professional_title=candidate.professional_title,
                candidate_score=candidate.candidate_score,
                coverage_score=candidate.coverage_score,
                matched_condition_labels=matched_labels,
                missing_condition_labels=tuple(
                    label for label in all_labels if label not in matched_set
                ),
                selected_for_final_context=candidate.candidate_id in final_ids,
            )
        )
    return tuple(diagnostics)


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
        raise ValueError(f"Robustness matrix field '{key}' must be text.")
    return item.strip()


def _required_list(value: Mapping[str, Any], key: str) -> list[Any]:
    item = value.get(key)
    if not isinstance(item, list):
        raise ValueError(f"Robustness matrix field '{key}' must be a list.")
    return item


def _required_mapping_list(
    value: Mapping[str, Any],
    key: str,
) -> list[Mapping[str, Any]]:
    items = _required_list(value, key)
    if not all(isinstance(item, dict) for item in items):
        raise ValueError(
            f"Robustness matrix list '{key}' must contain JSON objects."
        )
    return items


def _required_text_item(item: Any, key: str) -> str:
    if not isinstance(item, str) or not item.strip():
        raise ValueError(
            f"Robustness matrix list '{key}' must contain non-empty text."
        )
    return item.strip()


def _required_positive_integer(value: Mapping[str, Any], key: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int) or item < 1:
        raise ValueError(
            f"Robustness matrix field '{key}' must be a positive integer."
        )
    return item


def _required_non_negative_integer(
    value: Mapping[str, Any],
    key: str,
) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int) or item < 0:
        raise ValueError(
            f"Robustness matrix field '{key}' must be a non-negative integer."
        )
    return item
