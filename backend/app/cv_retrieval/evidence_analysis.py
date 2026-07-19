"""Deterministic lexical and relation-aware numeric CV evidence analysis.

Semantic similarity is valuable for recall, but recruiter constraints such as
"managed exactly eight engineers" require stricter evidence semantics. This
module keeps the implementation lightweight while enforcing three boundaries:

* lexical matches must correspond to real tokens in the evidence;
* related terms must occur locally rather than anywhere in a long chunk;
* numbers must be attached to the requested relationship, unit and operator.

Candidate-level aggregation remains a later WP6 responsibility.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
import unicodedata

from app.cv_retrieval.models import (
    RawCvRetrievalHit,
    RawCvRetrievalResult,
    RawCvRetrievalSource,
)


_TOKEN_PATTERN = re.compile(
    r"c\+\+|c#|\.net|[a-z0-9]+(?:[.-][a-z0-9]+)*",
    re.IGNORECASE,
)
_QUOTED_PATTERN = re.compile(r"[\"']([^\"']{2,100})[\"']")
_CLAUSE_SPLIT_PATTERN = re.compile(r"(?:[\r\n]+|[•▪◦●]+|[.!?;]+)")

# Question scaffolding does not help distinguish CV evidence. Technical terms,
# professions, languages, institutions, and leadership wording remain.
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "any",
    "are",
    "candidate",
    "candidates",
    "do",
    "does",
    "exactly",
    "find",
    "for",
    "from",
    "has",
    "have",
    "having",
    "in",
    "is",
    "me",
    "of",
    "or",
    "please",
    "show",
    "studied",
    "study",
    "the",
    "their",
    "to",
    "which",
    "who",
    "with",
}

_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
}

_MANAGEMENT_TERMS = {
    "lead",
    "leader",
    "leadership",
    "led",
    "manage",
    "managed",
    "management",
    "manager",
    "managing",
    "supervise",
    "supervised",
    "supervising",
}
_ENGINEERING_ROLE_TERMS = {
    "developer",
    "developers",
    "engineer",
    "engineers",
}
_PEOPLE_TERMS = {
    "employee",
    "employees",
    "member",
    "members",
    "people",
    "person",
    "report",
    "reports",
    "staff",
}
_TEAM_TERMS = {"squad", "squads", "team", "teams"}
_WORKFORCE_TERMS = _ENGINEERING_ROLE_TERMS | _PEOPLE_TERMS | _TEAM_TERMS
_DURATION_UNITS = {
    "day",
    "days",
    "month",
    "months",
    "week",
    "weeks",
    "year",
    "years",
    "y",
}
_PROFICIENCY_TERMS = {"native", "fluent", "professional", "intermediate"}
_PROFICIENCY_ALIASES = {
    "natively": "native",
    "fluently": "fluent",
    "professionally": "professional",
    "intermediately": "intermediate",
}
_LANGUAGE_FILLER_TERMS = {"language", "languages", "speaker", "speaking"}
_COMPARISON_FILLER_TERMS = {"at", "least", "most", "more", "less", "than", "over", "under", "minimum", "maximum", "exact", "exactly", "precisely", "up"}


@dataclass(frozen=True, slots=True)
class TextRelationConstraint:
    """A pair of lexical concepts that must co-occur locally in evidence."""

    relation: str
    terms: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.relation.strip():
            raise ValueError("Text relation name is required.")
        if len(self.terms) < 2 or any(not term.strip() for term in self.terms):
            raise ValueError("Text relation requires at least two terms.")


@dataclass(frozen=True, slots=True)
class NumericQueryConstraint:
    """One numeric requirement plus its operator and semantic relationship."""

    value: float
    display_value: str
    context_terms: tuple[str, ...]
    context_concepts: tuple[str, ...]
    operator: str = "eq"
    relation: str = "generic"
    target_terms: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not math.isfinite(self.value):
            raise ValueError("Numeric query constraint must be finite.")
        if not self.display_value.strip():
            raise ValueError("Numeric query constraint display value is required.")
        if self.operator not in {"eq", "gt", "gte", "lt", "lte"}:
            raise ValueError(f"Unsupported numeric operator: {self.operator}.")
        if self.relation not in {
            "generic",
            "team_size",
            "experience_duration",
        }:
            raise ValueError(f"Unsupported numeric relation: {self.relation}.")


@dataclass(frozen=True, slots=True)
class CvQueryEvidenceFeatures:
    """Deterministic lexical, relational, phrase, and numeric query signals."""

    normalized_text: str
    lexical_terms: tuple[str, ...]
    lexical_phrases: tuple[str, ...]
    numeric_constraints: tuple[NumericQueryConstraint, ...]
    text_relations: tuple[TextRelationConstraint, ...] = ()

    def __post_init__(self) -> None:
        if not self.normalized_text.strip():
            raise ValueError("Normalized recruiter question cannot be empty.")
        if len(self.lexical_terms) != len(set(self.lexical_terms)):
            raise ValueError("Lexical query terms must be unique.")
        if len(self.lexical_phrases) != len(set(self.lexical_phrases)):
            raise ValueError("Lexical query phrases must be unique.")

    @property
    def has_numeric_constraints(self) -> bool:
        return bool(self.numeric_constraints)


@dataclass(frozen=True, slots=True)
class CvEvidenceScore:
    """Separate semantic, lexical, and numeric components for one chunk."""

    semantic_score: float
    lexical_score: float
    numeric_score: float
    combined_score: float
    matched_terms: tuple[str, ...]
    matched_phrases: tuple[str, ...]
    matched_numeric_values: tuple[str, ...]
    contextual_numeric_match: bool
    matched_term_evidence: tuple[str, ...] = ()
    matched_numeric_contexts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "semantic_score",
            "lexical_score",
            "numeric_score",
            "combined_score",
        ):
            value = getattr(self, field_name)
            if not math.isfinite(value) or value < 0.0 or value > 1.0:
                raise ValueError(f"{field_name} must be between zero and one.")


@dataclass(frozen=True, slots=True)
class ScoredCvEvidenceHit:
    """One unique chunk reranked by semantic and exact-condition evidence."""

    rank: int
    raw_rank: int | None
    chunk_id: str
    distance: float | None
    text: str
    source: RawCvRetrievalSource
    score: CvEvidenceScore
    supplemental_exact_hit: bool = False

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise ValueError("Scored evidence rank must be positive.")
        if self.raw_rank is not None and self.raw_rank < 1:
            raise ValueError("Raw evidence rank must be positive when present.")
        if not self.chunk_id.strip() or not self.text.strip():
            raise ValueError("Scored evidence requires chunk identity and text.")
        if self.distance is not None and not math.isfinite(self.distance):
            raise ValueError("Scored evidence distance must be finite when present.")


@dataclass(frozen=True, slots=True)
class AssistedCvRetrievalResult:
    """Chunk-level assisted retrieval before candidate grouping and budgeting."""

    raw_result: RawCvRetrievalResult
    query_features: CvQueryEvidenceFeatures
    scanned_record_count: int
    duplicates_removed: int
    supplemental_hit_count: int
    hits: tuple[ScoredCvEvidenceHit, ...]

    def __post_init__(self) -> None:
        if self.scanned_record_count < 0:
            raise ValueError("Scanned record count cannot be negative.")
        if self.duplicates_removed < 0:
            raise ValueError("Duplicate count cannot be negative.")
        if self.supplemental_hit_count < 0:
            raise ValueError("Supplemental hit count cannot be negative.")
        if self.supplemental_hit_count > len(self.hits):
            raise ValueError("Supplemental hit count cannot exceed returned hits.")
        expected_ranks = tuple(range(1, len(self.hits) + 1))
        if tuple(hit.rank for hit in self.hits) != expected_ranks:
            raise ValueError("Scored evidence ranks must be consecutive.")

    @property
    def returned_result_count(self) -> int:
        return len(self.hits)

    @property
    def distinct_candidate_count(self) -> int:
        return len({hit.source.candidate_id for hit in self.hits})


def analyze_recruiter_question(text: str) -> CvQueryEvidenceFeatures:
    """Extract exact terms and typed relationships from a recruiter question."""

    normalized = normalize_search_text(text)
    raw_tokens = _tokenize(normalized)
    numeric_positions = {
        index: number
        for index, token in enumerate(raw_tokens)
        if (number := _parse_number_token(token)) is not None
    }

    lexical_terms = tuple(
        dict.fromkeys(
            canonicalize_lexical_term(token)
            for token in raw_tokens
            if token not in _STOP_WORDS
            and index_not_numeric(token)
            and canonicalize_lexical_term(token)
        )
    )
    text_relations = _extract_text_relations(raw_tokens)
    lexical_phrases = _extract_phrases(text, lexical_terms)
    numeric_constraints = tuple(
        _build_numeric_constraint(
            raw_tokens,
            position=index,
            value=value,
        )
        for index, value in numeric_positions.items()
    )
    return CvQueryEvidenceFeatures(
        normalized_text=normalized,
        lexical_terms=lexical_terms,
        lexical_phrases=lexical_phrases,
        numeric_constraints=numeric_constraints,
        text_relations=text_relations,
    )


def score_raw_hit(
    hit: RawCvRetrievalHit,
    features: CvQueryEvidenceFeatures,
    *,
    distance_metric: str,
) -> CvEvidenceScore:
    """Score one semantic hit while preserving each interpretable component."""

    return score_evidence_text(
        hit.text,
        features,
        semantic_score=semantic_relevance_from_distance(
            hit.distance,
            distance_metric,
        ),
    )


def score_evidence_text(
    text: str,
    features: CvQueryEvidenceFeatures,
    *,
    semantic_score: float = 0.0,
) -> CvEvidenceScore:
    """Score one chunk using real lexical spans and local numeric relations."""

    normalized = normalize_search_text(text)
    evidence_tokens = tuple(_tokenize(normalized))
    token_pairs = tuple(
        (token, canonicalize_lexical_term(token))
        for token in evidence_tokens
        if canonicalize_lexical_term(token)
    )

    relation_matches: list[tuple[TextRelationConstraint, str]] = []
    # Terms participating in a typed relation are never scored independently.
    # For example, "native" in "cloud-native" cannot satisfy a requested
    # native-language relation when the language term is absent.
    consumed_relation_terms: set[str] = {
        term
        for relation in features.text_relations
        for term in relation.terms
    }
    for relation in features.text_relations:
        matched_span = _match_text_relation(text, relation)
        if matched_span is None:
            continue
        relation_matches.append((relation, matched_span))

    matched_terms: list[str] = []
    matched_term_evidence: list[str] = []
    lexical_unit_count = len(features.text_relations)
    matched_lexical_units = len(relation_matches)

    for relation, matched_span in relation_matches:
        matched_terms.extend(relation.terms)
        matched_term_evidence.append(
            f"{'+'.join(relation.terms)}={matched_span}"
        )

    independent_terms = tuple(
        term
        for term in features.lexical_terms
        if term not in consumed_relation_terms
    )
    lexical_unit_count += len(independent_terms)
    for term in independent_terms:
        actual_match = _find_term_match(term, token_pairs)
        if actual_match is None:
            continue
        matched_lexical_units += 1
        matched_terms.append(term)
        matched_term_evidence.append(
            term if term == actual_match else f"{term}={actual_match}"
        )

    term_coverage = (
        matched_lexical_units / lexical_unit_count
        if lexical_unit_count
        else 0.0
    )
    matched_phrases = tuple(
        phrase
        for phrase in features.lexical_phrases
        if phrase in normalized
    )
    phrase_coverage = (
        len(matched_phrases) / len(features.lexical_phrases)
        if features.lexical_phrases
        else 0.0
    )
    lexical_score = min(1.0, term_coverage + (0.15 * phrase_coverage))

    numeric_scores: list[float] = []
    matched_numeric_values: list[str] = []
    matched_numeric_contexts: list[str] = []
    contextual_numeric_match = False
    for constraint in features.numeric_constraints:
        numeric_match = _score_numeric_constraint(text, constraint)
        numeric_scores.append(numeric_match.score)
        if numeric_match.contextual:
            matched_numeric_values.append(constraint.display_value)
            matched_numeric_contexts.extend(numeric_match.contexts)
            contextual_numeric_match = True

    numeric_score = (
        sum(numeric_scores) / len(numeric_scores)
        if numeric_scores
        else 0.0
    )

    if features.has_numeric_constraints:
        combined_score = (
            (0.40 * semantic_score)
            + (0.20 * lexical_score)
            + (0.40 * numeric_score)
        )
    else:
        combined_score = (0.70 * semantic_score) + (0.30 * lexical_score)

    return CvEvidenceScore(
        semantic_score=_clamp(semantic_score),
        lexical_score=_clamp(lexical_score),
        numeric_score=_clamp(numeric_score),
        combined_score=_clamp(combined_score),
        matched_terms=tuple(dict.fromkeys(matched_terms)),
        matched_phrases=matched_phrases,
        matched_numeric_values=tuple(dict.fromkeys(matched_numeric_values)),
        contextual_numeric_match=contextual_numeric_match,
        matched_term_evidence=tuple(dict.fromkeys(matched_term_evidence)),
        matched_numeric_contexts=tuple(
            dict.fromkeys(matched_numeric_contexts)
        ),
    )


def semantic_relevance_from_distance(distance: float, metric: str) -> float:
    """Convert supported Chroma distances into a larger-is-better score."""

    if not math.isfinite(distance):
        raise ValueError("Semantic distance must be finite.")
    if metric in {"cosine", "ip"}:
        return _clamp(1.0 - distance)
    if metric == "l2":
        return 1.0 / (1.0 + max(0.0, distance))
    raise ValueError(f"Unsupported semantic distance metric: {metric}.")


def normalize_search_text(text: str) -> str:
    """Normalize Unicode, case, punctuation, and whitespace for exact matching."""

    decomposed = unicodedata.normalize("NFKD", text).casefold()
    without_marks = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    separated = re.sub(r"[_‐‑‒–—-]+", " ", without_marks)
    tokens = _TOKEN_PATTERN.findall(separated)
    return " ".join(tokens)


def canonicalize_lexical_term(term: str) -> str:
    """Apply small transparent normalizations rather than opaque stemming."""

    normalized = term.casefold().strip(".-")
    if normalized in _PROFICIENCY_ALIASES:
        return _PROFICIENCY_ALIASES[normalized]
    if normalized in _MANAGEMENT_TERMS:
        return "manage"
    if normalized.endswith("ies") and len(normalized) > 4:
        return f"{normalized[:-3]}y"
    if (
        normalized.endswith("s")
        and len(normalized) > 4
        and not normalized.endswith("ss")
    ):
        return normalized[:-1]
    return normalized


def index_not_numeric(token: str) -> bool:
    """Return whether a token belongs in lexical rather than numeric signals."""

    return _parse_number_token(token) is None


@dataclass(frozen=True, slots=True)
class _NumericEvidenceMatch:
    score: float
    contextual: bool
    contexts: tuple[str, ...] = ()


def _extract_text_relations(
    tokens: tuple[str, ...],
) -> tuple[TextRelationConstraint, ...]:
    """Detect language/proficiency pairs without a static language list."""

    relations: list[TextRelationConstraint] = []
    for index, token in enumerate(tokens):
        proficiency = canonicalize_lexical_term(token)
        if proficiency not in _PROFICIENCY_TERMS:
            continue
        candidates: list[tuple[int, str]] = []
        for position in range(max(0, index - 3), min(len(tokens), index + 4)):
            if position == index:
                continue
            candidate = canonicalize_lexical_term(tokens[position])
            if (
                not candidate
                or candidate in _STOP_WORDS
                or candidate in _LANGUAGE_FILLER_TERMS
                or candidate in _PROFICIENCY_TERMS
                or candidate in _COMPARISON_FILLER_TERMS
            ):
                continue
            candidates.append((abs(position - index), candidate))
        if not candidates:
            continue
        _, language_term = min(candidates, key=lambda item: item[0])
        relation = TextRelationConstraint(
            relation="language_proficiency",
            terms=(language_term, proficiency),
        )
        if relation not in relations:
            relations.append(relation)
    return tuple(relations)


def _match_text_relation(
    text: str,
    relation: TextRelationConstraint,
) -> str | None:
    """Return the actual local evidence span for one typed text relation."""

    if relation.relation != "language_proficiency":
        return None
    language, proficiency = relation.terms
    for clause_tokens in _iter_clause_tokens(text):
        canonical = tuple(
            canonicalize_lexical_term(token) for token in clause_tokens
        )
        language_positions = [
            index for index, token in enumerate(canonical) if token == language
        ]
        proficiency_positions = [
            index
            for index, token in enumerate(canonical)
            if token == proficiency
        ]
        for language_index in language_positions:
            for proficiency_index in proficiency_positions:
                if abs(language_index - proficiency_index) > 3:
                    continue
                if (
                    proficiency == "native"
                    and proficiency_index > 0
                    and canonical[proficiency_index - 1] == "cloud"
                ):
                    continue
                start = min(language_index, proficiency_index)
                end = max(language_index, proficiency_index) + 1
                return " ".join(clause_tokens[start:end])
    return None


def _extract_phrases(
    original_text: str,
    lexical_terms: tuple[str, ...],
) -> tuple[str, ...]:
    quoted = [
        normalize_search_text(match.group(1))
        for match in _QUOTED_PATTERN.finditer(original_text)
    ]
    adjacent = [
        f"{left} {right}"
        for left, right in zip(lexical_terms, lexical_terms[1:])
    ]
    adjacent_triples = [
        " ".join(lexical_terms[index : index + 3])
        for index in range(max(0, len(lexical_terms) - 2))
    ]
    return tuple(
        phrase
        for phrase in dict.fromkeys((*quoted, *adjacent, *adjacent_triples))
        if phrase
    )


def _build_numeric_constraint(
    tokens: tuple[str, ...],
    *,
    position: int,
    value: float,
) -> NumericQueryConstraint:
    context_tokens = [
        canonicalize_lexical_term(token)
        for token in tokens
        if token not in _STOP_WORDS
        and _parse_number_token(token) is None
        and canonicalize_lexical_term(token)
    ]
    concepts = _context_concepts(tokens)
    relation = "generic"
    if {"management", "workforce"}.issubset(concepts):
        relation = "team_size"
    elif "experience_duration" in concepts:
        relation = "experience_duration"
    return NumericQueryConstraint(
        value=value,
        display_value=_format_number(value),
        context_terms=tuple(dict.fromkeys(context_tokens)),
        context_concepts=tuple(sorted(concepts)),
        operator=_detect_operator(tokens, position),
        relation=relation,
        target_terms=tuple(
            dict.fromkeys(
                canonicalize_lexical_term(token)
                for token in tokens
                if token.casefold() in _WORKFORCE_TERMS
            )
        ),
    )


def _score_numeric_constraint(
    text: str,
    constraint: NumericQueryConstraint,
) -> _NumericEvidenceMatch:
    """Require a value, operator and relationship in one local clause/window."""

    accepted_contexts: list[str] = []
    number_seen = False
    for clause_tokens in _iter_clause_tokens(text):
        for position, token in enumerate(clause_tokens):
            evidence_value = _parse_number_token(token)
            if evidence_value is None:
                continue
            if not _value_satisfies_operator(
                constraint,
                evidence_value=evidence_value,
                evidence_operator=_detect_operator(clause_tokens, position),
            ):
                continue
            number_seen = True
            if constraint.relation == "team_size":
                relation_matches = _matches_team_size_relation(
                    clause_tokens,
                    position,
                )
            elif constraint.relation == "experience_duration":
                relation_matches = _matches_experience_duration_relation(
                    clause_tokens,
                    position,
                )
            else:
                relation_matches = _matches_generic_numeric_context(
                    clause_tokens,
                    position,
                    constraint.context_terms,
                )
            if not relation_matches:
                continue
            accepted_contexts.append(
                _numeric_context_preview(clause_tokens, position)
            )

    if accepted_contexts:
        return _NumericEvidenceMatch(
            score=1.0,
            contextual=True,
            contexts=tuple(dict.fromkeys(accepted_contexts)),
        )
    # Relation-bound constraints deliberately receive no number-only credit.
    # This prevents durations, dates and phone fragments from masquerading as
    # team size or another exact recruiter requirement.
    if constraint.relation != "generic":
        return _NumericEvidenceMatch(score=0.0, contextual=False)
    return _NumericEvidenceMatch(
        score=0.10 if number_seen else 0.0,
        contextual=False,
    )


def _matches_team_size_relation(
    tokens: tuple[str, ...],
    number_position: int,
) -> bool:
    """Recognize team headcount, rejecting durations and unrelated numbers."""

    if _is_duration_number(tokens, number_position):
        return False
    local = _window(tokens, number_position, radius=8)
    # The counted workforce noun must be syntactically close to this number.
    # A wider window would incorrectly link "6 engineers" to a later
    # unrelated count such as "8 projects" in the same sentence.
    count_neighborhood = _window(tokens, number_position, radius=2)
    canonical_local = tuple(
        canonicalize_lexical_term(token) for token in local
    )
    canonical_count = tuple(
        canonicalize_lexical_term(token) for token in count_neighborhood
    )

    has_management = any(token in _MANAGEMENT_TERMS for token in local)
    has_direct_reports = _contains_sequence(canonical_local, ("direct", "report"))
    has_team_size = _contains_sequence(canonical_local, ("team", "size"))
    has_team_leadership = _contains_sequence(
        canonical_local,
        ("team", "leadership"),
    )
    has_workforce_count = any(
        token in {
            canonicalize_lexical_term(term)
            for term in _WORKFORCE_TERMS
        }
        for token in canonical_count
    )
    return (
        has_workforce_count
        and (
            has_management
            or has_direct_reports
            or has_team_size
            or has_team_leadership
        )
    )


def _matches_experience_duration_relation(
    tokens: tuple[str, ...],
    number_position: int,
) -> bool:
    local = _window(tokens, number_position, radius=5)
    lowered = {token.casefold() for token in local}
    return bool(lowered & _DURATION_UNITS) and bool(
        lowered & {"experience", "experienced", "career"}
    )


def _matches_generic_numeric_context(
    tokens: tuple[str, ...],
    number_position: int,
    context_terms: tuple[str, ...],
) -> bool:
    if not context_terms:
        return True
    pairs = tuple(
        (token, canonicalize_lexical_term(token))
        for token in _window(tokens, number_position, radius=8)
    )
    matched = sum(
        _find_term_match(term, pairs) is not None for term in context_terms
    )
    return matched / len(context_terms) >= 0.5


def _is_duration_number(tokens: tuple[str, ...], position: int) -> bool:
    following = {
        token.casefold()
        for token in tokens[position + 1 : position + 3]
    }
    nearby = {
        token.casefold()
        for token in _window(tokens, position, radius=4)
    }
    return bool(following & _DURATION_UNITS) or (
        bool(nearby & _DURATION_UNITS)
        and bool(nearby & {"experience", "experienced", "career", "since"})
    )


def _detect_operator(tokens: tuple[str, ...], position: int) -> str:
    before = tuple(token.casefold() for token in tokens[max(0, position - 4) : position])
    joined = " ".join(before)
    if any(marker in joined for marker in ("at least", "minimum", "no fewer than")):
        return "gte"
    if any(marker in joined for marker in ("more than", "over")):
        return "gt"
    if any(marker in joined for marker in ("at most", "maximum", "up to", "no more than")):
        return "lte"
    if any(marker in joined for marker in ("less than", "under")):
        return "lt"
    return "eq"


def _value_satisfies_operator(
    constraint: NumericQueryConstraint,
    *,
    evidence_value: float,
    evidence_operator: str,
) -> bool:
    query_value = constraint.value
    if constraint.operator == "eq":
        return evidence_operator == "eq" and evidence_value == query_value
    if constraint.operator == "gte":
        return evidence_operator not in {"lt", "lte"} and evidence_value >= query_value
    if constraint.operator == "gt":
        return evidence_operator not in {"lt", "lte"} and evidence_value > query_value
    if constraint.operator == "lte":
        return evidence_operator not in {"gt", "gte"} and evidence_value <= query_value
    if constraint.operator == "lt":
        return evidence_operator not in {"gt", "gte"} and evidence_value < query_value
    return False


def _context_concepts(tokens: tuple[str, ...] | list[str]) -> set[str]:
    concepts: set[str] = set()
    for token in tokens:
        lowered = token.casefold()
        if lowered in _MANAGEMENT_TERMS:
            concepts.add("management")
        if lowered in _WORKFORCE_TERMS:
            concepts.add("workforce")
        if lowered in _DURATION_UNITS or lowered in {
            "career",
            "experience",
            "experienced",
        }:
            concepts.add("experience_duration")
    return concepts


def _find_term_match(
    query_term: str,
    evidence_pairs: tuple[tuple[str, str], ...],
) -> str | None:
    """Return the actual token; aliases never create invisible evidence."""

    for actual, canonical in evidence_pairs:
        if canonical == query_term:
            return actual.casefold()

    alias_family: set[str] | None = None
    if query_term == "manage":
        alias_family = {
            canonicalize_lexical_term(term) for term in _MANAGEMENT_TERMS
        }
    elif query_term in {
        canonicalize_lexical_term(term)
        for term in _ENGINEERING_ROLE_TERMS
    }:
        alias_family = {
            canonicalize_lexical_term(term)
            for term in _ENGINEERING_ROLE_TERMS
        }
    elif query_term in {
        canonicalize_lexical_term(term) for term in _PEOPLE_TERMS
    }:
        alias_family = {
            canonicalize_lexical_term(term) for term in _PEOPLE_TERMS
        }
    elif query_term in {
        canonicalize_lexical_term(term) for term in _TEAM_TERMS
    }:
        alias_family = {
            canonicalize_lexical_term(term) for term in _TEAM_TERMS
        }
    if alias_family is None:
        return None
    for actual, canonical in evidence_pairs:
        if canonical in alias_family:
            return actual.casefold()
    return None


def _iter_clause_tokens(text: str) -> tuple[tuple[str, ...], ...]:
    clauses: list[tuple[str, ...]] = []
    for raw_clause in _CLAUSE_SPLIT_PATTERN.split(text):
        normalized = normalize_search_text(raw_clause)
        tokens = _tokenize(normalized)
        if tokens:
            clauses.append(tokens)
    return tuple(clauses)


def _window(
    tokens: tuple[str, ...],
    position: int,
    *,
    radius: int,
) -> tuple[str, ...]:
    return tokens[max(0, position - radius) : min(len(tokens), position + radius + 1)]


def _numeric_context_preview(
    tokens: tuple[str, ...],
    position: int,
) -> str:
    return " ".join(_window(tokens, position, radius=7))


def _contains_sequence(
    tokens: tuple[str, ...],
    sequence: tuple[str, ...],
) -> bool:
    width = len(sequence)
    return any(
        tokens[index : index + width] == sequence
        for index in range(max(0, len(tokens) - width + 1))
    )


def _parse_number_token(token: str) -> float | None:
    lowered = token.casefold()
    if lowered in _NUMBER_WORDS:
        return float(_NUMBER_WORDS[lowered])
    if re.fullmatch(r"\d+(?:\.\d+)?", lowered):
        return float(lowered)
    return None


def _tokenize(normalized_text: str) -> tuple[str, ...]:
    return tuple(_TOKEN_PATTERN.findall(normalized_text.casefold()))


def _format_number(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
