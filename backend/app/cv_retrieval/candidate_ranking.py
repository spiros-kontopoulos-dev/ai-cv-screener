"""Candidate-level CV evidence grouping, coverage scoring, and balancing.

Chunk retrieval deliberately optimizes recall. Recruiter answers, however, are
about people rather than individual text fragments. This module converts honest
chunk scores into one bounded result per stable candidate ID while preserving
all source evidence used to justify the rank.

The ranking rules are intentionally deterministic:

* query conditions are explicit and inspectable;
* one best evidence chunk supports each condition;
* repeated chunks cannot increase condition coverage;
* a small evidence cap prevents verbose CVs from dominating;
* explicit candidate names are alternatives in comparison questions.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal

from app.cv_retrieval.evidence_analysis import (
    AssistedCvRetrievalResult,
    CvQueryEvidenceFeatures,
    NumericQueryConstraint,
    ScoredCvEvidenceHit,
    canonicalize_lexical_term,
    normalize_search_text,
)


ConditionKind = Literal["identity", "relation", "numeric", "phrase", "term"]

_LOW_SIGNAL_TERMS = {
    "background",
    "candidate",
    "compare",
    "experience",
    "experienced",
    "knowledge",
    "role",
    "skill",
    "speak",
    "speaker",
    "work",
    "working",
}
_ROLE_HEAD_TERMS = {
    "analyst",
    "architect",
    "developer",
    "designer",
    "engineer",
    "engineering",
    "manager",
    "scientist",
}
_TEAM_RELATION_TERMS = {
    "developer",
    "engineer",
    "lead",
    "leader",
    "leadership",
    "manage",
    "management",
    "manager",
    "member",
    "people",
    "person",
    "report",
    "staff",
    "squad",
    "supervise",
    "team",
}
_EXPERIENCE_RELATION_TERMS = {
    "day",
    "experience",
    "month",
    "week",
    "year",
}


@dataclass(frozen=True, slots=True)
class CandidateQueryCondition:
    """One recruiter requirement that candidate evidence may satisfy."""

    key: str
    label: str
    kind: ConditionKind
    weight: float
    terms: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = ()
    numeric_value: str | None = None

    def __post_init__(self) -> None:
        if not self.key.strip() or not self.label.strip():
            raise ValueError("Candidate condition identity and label are required.")
        if self.kind not in {"identity", "relation", "numeric", "phrase", "term"}:
            raise ValueError(f"Unsupported candidate condition kind: {self.kind}.")
        if not math.isfinite(self.weight) or self.weight <= 0.0:
            raise ValueError("Candidate condition weight must be positive and finite.")
        if self.kind == "identity" and not self.alternatives:
            raise ValueError("Identity conditions require candidate-name alternatives.")
        if self.kind in {"relation", "phrase"} and len(self.terms) < 2:
            raise ValueError(f"{self.kind.title()} conditions require multiple terms.")
        if self.kind == "term" and len(self.terms) != 1:
            raise ValueError("Term conditions require exactly one term.")
        if self.kind == "numeric" and self.numeric_value is None:
            raise ValueError("Numeric conditions require a display value.")


@dataclass(frozen=True, slots=True)
class CandidateConditionMatch:
    """The best source chunk supporting one candidate-level condition."""

    condition: CandidateQueryCondition
    chunk_id: str
    assisted_rank: int
    evidence_score: float

    def __post_init__(self) -> None:
        if not self.chunk_id.strip() or self.assisted_rank < 1:
            raise ValueError("Condition matches require valid chunk identity and rank.")
        if (
            not math.isfinite(self.evidence_score)
            or self.evidence_score < 0.0
            or self.evidence_score > 1.0
        ):
            raise ValueError("Condition evidence score must be between zero and one.")


@dataclass(frozen=True, slots=True)
class CandidateEvidenceSelection:
    """One bounded evidence chunk selected for a candidate result."""

    order: int
    hit: ScoredCvEvidenceHit
    condition_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.order < 1:
            raise ValueError("Candidate evidence order must be positive.")
        if len(self.condition_keys) != len(set(self.condition_keys)):
            raise ValueError("Candidate evidence condition keys must be unique.")


@dataclass(frozen=True, slots=True)
class RankedCvCandidate:
    """One candidate-level result with bounded, source-traceable evidence."""

    rank: int
    candidate_id: str
    candidate_name: str | None
    professional_title: str | None
    candidate_score: float
    coverage_score: float
    condition_quality_score: float
    semantic_support_score: float
    matched_conditions: tuple[CandidateConditionMatch, ...]
    total_condition_count: int
    total_candidate_hit_count: int
    evidence: tuple[CandidateEvidenceSelection, ...]

    def __post_init__(self) -> None:
        if self.rank < 1 or not self.candidate_id.strip():
            raise ValueError("Ranked candidates require rank and candidate ID.")
        for field_name in (
            "candidate_score",
            "coverage_score",
            "condition_quality_score",
            "semantic_support_score",
        ):
            value = getattr(self, field_name)
            if not math.isfinite(value) or value < 0.0 or value > 1.0:
                raise ValueError(f"{field_name} must be between zero and one.")
        if self.total_condition_count < len(self.matched_conditions):
            raise ValueError("Matched conditions cannot exceed total query conditions.")
        if self.total_candidate_hit_count < len(self.evidence):
            raise ValueError("Selected evidence cannot exceed candidate hit count.")
        if tuple(item.order for item in self.evidence) != tuple(
            range(1, len(self.evidence) + 1)
        ):
            raise ValueError("Candidate evidence order must be consecutive.")
        if any(
            item.hit.source.candidate_id != self.candidate_id
            for item in self.evidence
        ):
            raise ValueError("Candidate evidence cannot cross candidate IDs.")

    @property
    def matched_condition_count(self) -> int:
        return len(self.matched_conditions)

    @property
    def complete_condition_coverage(self) -> bool:
        return (
            self.total_condition_count > 0
            and self.matched_condition_count == self.total_condition_count
        )


@dataclass(frozen=True, slots=True)
class CandidateCvRetrievalResult:
    """Candidate-aware ranking output before final context budgeting."""

    assisted_result: AssistedCvRetrievalResult
    conditions: tuple[CandidateQueryCondition, ...]
    requested_candidate_limit: int
    evidence_per_candidate_limit: int
    grouped_candidate_count: int
    candidates: tuple[RankedCvCandidate, ...]

    def __post_init__(self) -> None:
        if self.requested_candidate_limit < 1:
            raise ValueError("Requested candidate limit must be positive.")
        if self.evidence_per_candidate_limit < 1:
            raise ValueError("Evidence-per-candidate limit must be positive.")
        if self.grouped_candidate_count < len(self.candidates):
            raise ValueError("Grouped candidate count cannot be below returned count.")
        if len(self.candidates) > self.requested_candidate_limit:
            raise ValueError("Candidate result exceeded the requested limit.")
        if tuple(candidate.rank for candidate in self.candidates) != tuple(
            range(1, len(self.candidates) + 1)
        ):
            raise ValueError("Candidate ranks must be consecutive.")

    @property
    def returned_candidate_count(self) -> int:
        return len(self.candidates)


def build_candidate_conditions(
    features: CvQueryEvidenceFeatures,
    *,
    candidate_names: tuple[str, ...] = (),
) -> tuple[CandidateQueryCondition, ...]:
    """Build non-overlapping conditions from query features and known names."""

    conditions: list[CandidateQueryCondition] = []
    consumed_terms: set[str] = set()

    explicit_names = tuple(
        dict.fromkeys(
            normalize_search_text(name)
            for name in candidate_names
            if name and normalize_search_text(name) in features.normalized_text
        )
    )
    # Query analysis canonicalizes lexical tokens (for example, ``Lukas``
    # becomes ``luka`` through the transparent plural-like normalization).
    # Canonicalize name tokens through the same function before excluding them,
    # otherwise a person's name may leak into the skill conditions.
    explicit_name_tokens = {
        canonicalize_lexical_term(token)
        for name in explicit_names
        for token in name.split()
        if canonicalize_lexical_term(token)
    }
    if explicit_names:
        conditions.append(
            CandidateQueryCondition(
                key="identity:explicit-candidate",
                label="explicitly requested candidate",
                kind="identity",
                weight=2.0,
                alternatives=explicit_names,
            )
        )
        consumed_terms.update(explicit_name_tokens)

    for relation in features.text_relations:
        key = f"relation:{relation.relation}:{'+'.join(relation.terms)}"
        conditions.append(
            CandidateQueryCondition(
                key=key,
                label=" ".join(relation.terms),
                kind="relation",
                weight=1.5,
                terms=relation.terms,
            )
        )
        consumed_terms.update(relation.terms)

    for index, constraint in enumerate(features.numeric_constraints):
        conditions.append(_numeric_condition(constraint, index=index))
        if constraint.relation == "team_size":
            consumed_terms.update(
                term
                for term in features.lexical_terms
                if term in _TEAM_RELATION_TERMS
            )
        elif constraint.relation == "experience_duration":
            consumed_terms.update(
                term
                for term in features.lexical_terms
                if term in _EXPERIENCE_RELATION_TERMS
            )

    remaining_terms = [
        term
        for term in features.lexical_terms
        if term not in consumed_terms and term not in _LOW_SIGNAL_TERMS
    ]

    # Role phrases are one semantic condition rather than two independently
    # countable words. This prevents "backend" and "engineer" from doubling a
    # single concept while still allowing the phrase to be supported by one CV
    # section and other conditions by different sections.
    phrase_consumed: set[str] = set()
    for left, right in zip(remaining_terms, remaining_terms[1:]):
        phrase = f"{left} {right}"
        if right not in _ROLE_HEAD_TERMS:
            continue
        if phrase not in features.normalized_text:
            continue
        conditions.append(
            CandidateQueryCondition(
                key=f"phrase:{phrase}",
                label=phrase,
                kind="phrase",
                weight=1.25,
                terms=(left, right),
            )
        )
        phrase_consumed.update((left, right))

    for term in remaining_terms:
        if term in phrase_consumed:
            continue
        conditions.append(
            CandidateQueryCondition(
                key=f"term:{term}",
                label=term,
                kind="term",
                weight=1.0,
                terms=(term,),
            )
        )

    return tuple(conditions)


def rank_candidates(
    assisted_result: AssistedCvRetrievalResult,
    *,
    candidate_limit: int,
    evidence_limit: int,
) -> CandidateCvRetrievalResult:
    """Group scored chunks by candidate and return balanced candidate ranks."""

    if candidate_limit < 1 or evidence_limit < 1:
        raise ValueError("Candidate and evidence limits must be positive.")

    grouped: dict[str, list[ScoredCvEvidenceHit]] = {}
    for hit in assisted_result.hits:
        grouped.setdefault(hit.source.candidate_id, []).append(hit)

    candidate_names = tuple(
        dict.fromkeys(
            hit.source.candidate_name
            for hit in assisted_result.hits
            if hit.source.candidate_name
        )
    )
    conditions = build_candidate_conditions(
        assisted_result.query_features,
        candidate_names=candidate_names,
    )

    unranked = [
        _rank_one_candidate(
            candidate_id,
            hits,
            conditions=conditions,
            evidence_limit=evidence_limit,
        )
        for candidate_id, hits in grouped.items()
    ]
    ordered = sorted(
        unranked,
        key=lambda candidate: (
            -candidate.candidate_score,
            -candidate.coverage_score,
            -candidate.condition_quality_score,
            -candidate.semantic_support_score,
            min(item.hit.rank for item in candidate.evidence),
            candidate.candidate_id,
        ),
    )
    ranked = tuple(
        _replace_candidate_rank(candidate, rank)
        for rank, candidate in enumerate(ordered[:candidate_limit], start=1)
    )
    return CandidateCvRetrievalResult(
        assisted_result=assisted_result,
        conditions=conditions,
        requested_candidate_limit=candidate_limit,
        evidence_per_candidate_limit=evidence_limit,
        grouped_candidate_count=len(grouped),
        candidates=ranked,
    )


def _rank_one_candidate(
    candidate_id: str,
    hits: list[ScoredCvEvidenceHit],
    *,
    conditions: tuple[CandidateQueryCondition, ...],
    evidence_limit: int,
) -> RankedCvCandidate:
    """Calculate one candidate score without rewarding repeated evidence."""

    _validate_candidate_identity(candidate_id, hits)
    condition_matches = tuple(
        match
        for condition in conditions
        if (match := _best_condition_match(condition, candidate_id, hits))
        is not None
    )

    total_weight = sum(condition.weight for condition in conditions)
    matched_weight = sum(match.condition.weight for match in condition_matches)
    coverage_score = matched_weight / total_weight if total_weight else 0.0
    condition_quality_score = (
        sum(
            match.condition.weight * match.evidence_score
            for match in condition_matches
        )
        / total_weight
        if total_weight
        else 0.0
    )
    semantic_support_score = max(
        (hit.score.semantic_score for hit in hits),
        default=0.0,
    )

    if conditions:
        candidate_score = (
            (0.55 * coverage_score)
            + (0.30 * condition_quality_score)
            + (0.15 * semantic_support_score)
        )
    else:
        best_combined = max(
            (hit.score.combined_score for hit in hits),
            default=0.0,
        )
        candidate_score = (
            (0.75 * best_combined) + (0.25 * semantic_support_score)
        )

    selected_evidence = _select_candidate_evidence(
        hits,
        condition_matches=condition_matches,
        evidence_limit=evidence_limit,
    )
    first_source = hits[0].source
    return RankedCvCandidate(
        rank=1,
        candidate_id=candidate_id,
        candidate_name=first_source.candidate_name,
        professional_title=first_source.professional_title,
        candidate_score=_clamp(candidate_score),
        coverage_score=_clamp(coverage_score),
        condition_quality_score=_clamp(condition_quality_score),
        semantic_support_score=_clamp(semantic_support_score),
        matched_conditions=condition_matches,
        total_condition_count=len(conditions),
        total_candidate_hit_count=len(hits),
        evidence=selected_evidence,
    )


def _best_condition_match(
    condition: CandidateQueryCondition,
    candidate_id: str,
    hits: list[ScoredCvEvidenceHit],
) -> CandidateConditionMatch | None:
    candidates: list[tuple[float, ScoredCvEvidenceHit]] = []
    for hit in hits:
        evidence_score = _condition_evidence_score(
            condition,
            candidate_id=candidate_id,
            hit=hit,
        )
        if evidence_score <= 0.0:
            continue
        candidates.append((evidence_score, hit))
    if not candidates:
        return None
    evidence_score, hit = max(
        candidates,
        key=lambda item: (
            item[0],
            item[1].score.combined_score,
            item[1].score.semantic_score,
            -item[1].rank,
        ),
    )
    return CandidateConditionMatch(
        condition=condition,
        chunk_id=hit.chunk_id,
        assisted_rank=hit.rank,
        evidence_score=evidence_score,
    )


def _condition_evidence_score(
    condition: CandidateQueryCondition,
    *,
    candidate_id: str,
    hit: ScoredCvEvidenceHit,
) -> float:
    if condition.kind == "identity":
        candidate_name = normalize_search_text(hit.source.candidate_name or "")
        return 1.0 if candidate_name in condition.alternatives else 0.0
    if condition.kind == "numeric":
        if (
            condition.numeric_value in hit.score.matched_numeric_values
            and hit.score.contextual_numeric_match
        ):
            return hit.score.numeric_score
        return 0.0
    if condition.kind == "relation":
        return (
            _lexical_evidence_strength(hit)
            if all(term in hit.score.matched_terms for term in condition.terms)
            else 0.0
        )
    if condition.kind == "phrase":
        if _is_role_phrase(condition):
            return _role_phrase_evidence_score(condition, hit)
        return (
            _lexical_evidence_strength(hit)
            if _contains_canonical_phrase(hit.text, condition.terms)
            else 0.0
        )
    if condition.kind == "term":
        return (
            _lexical_evidence_strength(hit)
            if condition.terms[0] in hit.score.matched_terms
            else 0.0
        )
    raise ValueError(f"Unsupported candidate condition kind: {condition.kind}.")



def _is_role_phrase(condition: CandidateQueryCondition) -> bool:
    """Return whether a phrase describes the candidate's profession/domain."""

    return bool(
        condition.terms
        and condition.terms[-1] in _ROLE_HEAD_TERMS
    )


def _role_phrase_evidence_score(
    condition: CandidateQueryCondition,
    hit: ScoredCvEvidenceHit,
) -> float:
    """Score role evidence only when it describes the candidate themselves.

    A role phrase can appear in a CV because the candidate collaborated with
    people in that role. Those mentions must not satisfy a recruiter condition
    about the candidate's own profession. We therefore accept role evidence
    from the canonical professional title, or from the title-like prefix of an
    identity, professional-summary, or experience section.
    """

    role_terms = tuple(_canonical_role_token(term) for term in condition.terms)
    title_tokens = _canonical_role_tokens(hit.source.professional_title or "")
    if _contains_token_sequence(title_tokens, role_terms):
        return _lexical_evidence_strength(hit)

    section_prefix_limits = {
        "identity": 18,
        "professional_summary": 20,
        "experience": 5,
    }
    prefix_limit = section_prefix_limits.get(hit.source.section_name)
    if prefix_limit is None:
        return 0.0

    evidence_tokens = _canonical_role_tokens(hit.text)[:prefix_limit]
    if not _contains_token_sequence(evidence_tokens, role_terms):
        return 0.0
    return _lexical_evidence_strength(hit)


def _contains_canonical_phrase(
    text: str,
    terms: tuple[str, ...],
) -> bool:
    """Match a phrase by whole canonical tokens, never by substring prefix."""

    tokens = tuple(
        canonicalize_lexical_term(token)
        for token in normalize_search_text(text).split()
        if canonicalize_lexical_term(token)
    )
    expected = tuple(canonicalize_lexical_term(term) for term in terms)
    return _contains_token_sequence(tokens, expected)


def _canonical_role_tokens(text: str) -> tuple[str, ...]:
    return tuple(
        _canonical_role_token(token)
        for token in normalize_search_text(text).split()
        if _canonical_role_token(token)
    )


def _canonical_role_token(token: str) -> str:
    canonical = canonicalize_lexical_term(token)
    if canonical == "engineering":
        return "engineer"
    return canonical


def _contains_token_sequence(
    tokens: tuple[str, ...],
    expected: tuple[str, ...],
) -> bool:
    if not expected or len(expected) > len(tokens):
        return False
    width = len(expected)
    return any(
        tokens[index : index + width] == expected
        for index in range(len(tokens) - width + 1)
    )

def _lexical_evidence_strength(hit: ScoredCvEvidenceHit) -> float:
    """Combine exact lexical confidence with bounded semantic support."""

    return _clamp(
        (0.70 * hit.score.lexical_score)
        + (0.20 * hit.score.semantic_score)
        + (0.10 * hit.score.combined_score)
    )


def _select_candidate_evidence(
    hits: list[ScoredCvEvidenceHit],
    *,
    condition_matches: tuple[CandidateConditionMatch, ...],
    evidence_limit: int,
) -> tuple[CandidateEvidenceSelection, ...]:
    """Greedily cover conditions, then fill remaining bounded evidence slots."""

    matches_by_chunk: dict[str, list[CandidateConditionMatch]] = {}
    for match in condition_matches:
        matches_by_chunk.setdefault(match.chunk_id, []).append(match)

    selected: list[ScoredCvEvidenceHit] = []
    uncovered = {match.condition.key for match in condition_matches}
    available = list(hits)
    while uncovered and available and len(selected) < evidence_limit:
        best = max(
            available,
            key=lambda hit: (
                sum(
                    match.condition.weight
                    for match in matches_by_chunk.get(hit.chunk_id, ())
                    if match.condition.key in uncovered
                ),
                hit.score.combined_score,
                hit.score.semantic_score,
                -hit.rank,
            ),
        )
        covered = {
            match.condition.key
            for match in matches_by_chunk.get(best.chunk_id, ())
            if match.condition.key in uncovered
        }
        if not covered:
            break
        selected.append(best)
        uncovered.difference_update(covered)
        available.remove(best)

    for hit in sorted(
        available,
        key=lambda item: (
            item.score.combined_score,
            item.score.semantic_score,
            -item.rank,
        ),
        reverse=True,
    ):
        if len(selected) >= evidence_limit:
            break
        selected.append(hit)

    return tuple(
        CandidateEvidenceSelection(
            order=order,
            hit=hit,
            condition_keys=tuple(
                match.condition.key
                for match in matches_by_chunk.get(hit.chunk_id, ())
            ),
        )
        for order, hit in enumerate(selected, start=1)
    )


def _numeric_condition(
    constraint: NumericQueryConstraint,
    *,
    index: int,
) -> CandidateQueryCondition:
    operator_labels = {
        "eq": "exactly",
        "gt": "more than",
        "gte": "at least",
        "lt": "less than",
        "lte": "at most",
    }
    relation_label = {
        "team_size": "team size",
        "experience_duration": "experience duration",
        "generic": "numeric requirement",
    }[constraint.relation]
    return CandidateQueryCondition(
        key=(
            f"numeric:{index}:{constraint.relation}:"
            f"{constraint.operator}:{constraint.display_value}"
        ),
        label=(
            f"{relation_label} {operator_labels[constraint.operator]} "
            f"{constraint.display_value}"
        ),
        kind="numeric",
        weight=2.0 if constraint.relation == "team_size" else 1.5,
        numeric_value=constraint.display_value,
    )


def _validate_candidate_identity(
    candidate_id: str,
    hits: list[ScoredCvEvidenceHit],
) -> None:
    if not hits:
        raise ValueError(f"Candidate {candidate_id} has no evidence hits.")
    names = {
        hit.source.candidate_name
        for hit in hits
        if hit.source.candidate_name is not None
    }
    titles = {
        hit.source.professional_title
        for hit in hits
        if hit.source.professional_title is not None
    }
    if len(names) > 1:
        raise ValueError(
            f"Candidate {candidate_id} has conflicting names in stored evidence."
        )
    if len(titles) > 1:
        raise ValueError(
            f"Candidate {candidate_id} has conflicting professional titles."
        )


def _replace_candidate_rank(
    candidate: RankedCvCandidate,
    rank: int,
) -> RankedCvCandidate:
    return RankedCvCandidate(
        rank=rank,
        candidate_id=candidate.candidate_id,
        candidate_name=candidate.candidate_name,
        professional_title=candidate.professional_title,
        candidate_score=candidate.candidate_score,
        coverage_score=candidate.coverage_score,
        condition_quality_score=candidate.condition_quality_score,
        semantic_support_score=candidate.semantic_support_score,
        matched_conditions=candidate.matched_conditions,
        total_condition_count=candidate.total_condition_count,
        total_candidate_hit_count=candidate.total_candidate_hit_count,
        evidence=candidate.evidence,
    )


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
