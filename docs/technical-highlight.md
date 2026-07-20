# Technical Highlight: Grounded Hybrid Retrieval with Relation-Aware Candidate Evidence

> **Purpose**
>
> This document is the public technical explanation and video walkthrough guide for the final delivery. It focuses on one technical highlight: the custom evidence layer that sits between semantic CV retrieval and grounded answer generation.
>
> The code excerpts below come from the current committed source snapshot. Line numbers are included as navigation aids and may move after future edits.

---

## Summary explanation

The most distinctive part of the AI CV Screener is not the use of embeddings or a vector database by itself. The important engineering work is the evidence-verification layer built on top of semantic retrieval.

During live testing, the system exposed a subtle precision problem. A semantic search for:

> **Who managed exactly eight engineers?**

could retrieve a candidate whose CV mentioned **eight years of experience**, because both texts were related to engineering seniority and leadership. The vector result was semantically relevant, but it did not prove the requested relationship.

The solution separates responsibilities:

1. **Embeddings provide broad semantic recall.**
2. **Deterministic query analysis identifies typed requirements**, such as team size, experience duration, education, language proficiency, role, and comparison operator.
3. **Clause-local evidence validation checks whether the requested fact is actually present in the correct relationship.**
4. **Evidence is grouped and scored by candidate**, rather than treating every text chunk as an independent answer.
5. **Only candidates that satisfy the support rules enter the bounded context sent to the answer provider.**
6. **A provider-free robustness evaluator tests paraphrase families and negative controls through the real retrieval pipeline.**

This design fixed the exact-number failure and later generalized to natural-language variations involving education, total experience, native languages, role aliases, accessibility, QA automation, compound technology requirements, and named-candidate comparisons.

The measurable result was:

| Evaluation stage | Result |
|---|---:|
| Initial robustness baseline | 18 of 48 scenarios passed |
| Confirmed failures | 30 |
| Expanded post-refactor matrix | 50 of 50 scenarios passed |
| Hosted-provider calls during evaluation | 0 |
| Negative controls | Remained unsupported |

The key principle is:

> **Semantic relevance shows that evidence is related to a question. Deterministic relation-aware validation establishes that the evidence actually proves the requested fact.**

---

## 1. Why this is the selected technical highlight

The delivery asks for one specific part of the code or logic that demonstrates technical depth, a challenging problem, or a creative solution.

This highlight is the strongest choice because it is:

- directly connected to the backend and AI workflow;
- based on a real retrieval failure discovered through live output;
- more substantial than a standard vector-store integration;
- implemented through custom, transparent Python logic;
- measurable through before-and-after evaluation;
- protected by positive, adversarial, and unsupported regression cases;
- easy to demonstrate with one clear question;
- general enough to support many future recruiter queries.

The central story is not:

> “The project uses ChromaDB and RAG.”

The central story is:

> “The project measured where naive semantic retrieval failed in CV screening, then added typed query interpretation, relation-aware exact evidence validation, candidate-level aggregation, bounded context construction, and a provider-free robustness evaluator.”

---

## 2. The failure that exposed the problem

### Example question

```text
Who managed exactly eight engineers?
```

### Semantically related but incorrect evidence

```text
Senior Python backend engineer with 8 years of experience...
```

The number `8` is present and the text concerns engineering seniority, but it does not prove team size.

### Correct evidence

```text
Team leadership: managed 8 people.
Led a team of exactly 8 engineers responsible for backend services.
```

This evidence contains the complete local relationship:

```text
management action + value 8 + workforce target
```

### Why embeddings alone could not guarantee the answer

Dense embeddings are designed to capture related meaning. They are not exact field filters and do not inherently know whether a number refers to:

- years of experience;
- engineers managed;
- projects completed;
- a date;
- a percentage;
- a phone-number fragment;
- a technology duration.

The retrieval pipeline therefore needed a second dimension of evidence quality:

```text
Is the chunk semantically relevant?
                +
Does the chunk prove the requested relationship?
```

---

## 3. Final retrieval architecture

```text
Recruiter question
        |
        v
Typed query analysis
- lexical terms
- relation constraints
- education constraints
- numeric value + operator + relation
        |
        v
Broad semantic retrieval from Chroma
        |
        v
Bounded exact scan of persisted chunk text
        |
        v
Clause-local relation validation
        |
        v
Deduplicate and rerank source-traceable chunks
        |
        v
Group evidence by candidate_id
        |
        v
Candidate condition coverage and quality scoring
        |
        v
Supported / partial / unsupported decision
        |
        v
Bounded candidate-owned context
        |
        v
Hosted answer provider only when support exists
```

### Responsibility boundaries

| Layer | Responsibility |
|---|---|
| Embedding model and Chroma | Retrieve broadly related CV evidence |
| Query analysis | Convert recruiter wording into inspectable requirements |
| Exact evidence validation | Verify that values and concepts belong to the requested relation |
| Candidate ranking | Aggregate evidence belonging to the same person |
| Final retrieval | Enforce support thresholds and context budgets |
| Answer provider | Explain only the grounded evidence it receives |
| Robustness evaluator | Test the retrieval behavior without generating hosted answers |

---

## 4. Main source files

| File | Responsibility in the technical highlight |
|---|---|
| `backend/app/cv_retrieval/evidence_analysis.py` | Normalizes questions, extracts typed relations and numeric constraints, validates local evidence, and produces semantic/lexical/numeric scores |
| `backend/app/cv_retrieval/assisted_retrieval.py` | Combines semantic top-k recall with a bounded exact scan of stored chunk text |
| `backend/app/cv_retrieval/candidate_ranking.py` | Converts query features into candidate conditions, groups chunks by `candidate_id`, calculates condition coverage, and selects bounded evidence |
| `backend/app/cv_retrieval/candidate_retrieval.py` | Connects assisted chunk retrieval to candidate-level ranking |
| `backend/app/cv_retrieval/final_retrieval.py` | Applies supported/partial/unsupported thresholds and builds source-traceable context under hard budgets |
| `backend/app/cv_retrieval/robustness_evaluation.py` | Runs paraphrase families through the real final retriever and records parser, candidate, source, budget, and outcome diagnostics |
| `backend/app/scripts/evaluate_cv_query_robustness.py` | Exposes the provider-free evaluator as a CLI with filters, verbose diagnostics, JSON output, and strict regression mode |
| `backend/app/dataset/cv_query_robustness_matrix.json` | Defines the 13 query families and 50 expected scenarios |
| `backend/tests/test_cv_evidence_analysis.py` | Protects typed numeric relationships and rejects dates, durations, phone numbers, and unrelated counts |
| `backend/tests/test_cv_candidate_ranking.py` | Protects candidate grouping, evidence ownership, coverage scoring, and balanced selection |
| `backend/tests/test_cv_query_understanding.py` | Protects paraphrase handling, education binding, language idioms, role aliases, and numeric operators |
| `backend/tests/test_cv_query_robustness_evaluation.py` | Protects the matrix contract and evaluator diagnostics |
| `backend/tests/test_evaluate_cv_query_robustness_cli.py` | Protects CLI output, JSON persistence, and strict-mode behavior |

---

# 5. Code walkthrough

## Code excerpt 1 — Represent numbers as typed relationships

**File:** `backend/app/cv_retrieval/evidence_analysis.py`  
**Current lines:** 295–319

```python
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
```

### Explanation

The system does not store `8` as an isolated keyword. It records:

```text
value = 8
operator = equality
relation = team_size
```

The same structure supports:

```text
more than 5 years  -> value=5, operator=gt,  relation=experience_duration
at least 6 years   -> value=6, operator=gte, relation=experience_duration
exactly 8 people   -> value=8, operator=eq,  relation=team_size
```

This is what prevents one kind of number from satisfying another numeric requirement.

---

## Code excerpt 2 — Remove recruiter scaffolding from factual evidence

**File:** `backend/app/cv_retrieval/evidence_analysis.py`  
**Current lines:** 430–452

```python
def analyze_recruiter_question(text: str) -> CvQueryEvidenceFeatures:
    """Extract typed facts while discarding conversational query scaffolding."""

    normalized = normalize_search_text(text)
    raw_tokens = _tokenize(normalized)
    numeric_positions = {
        index: number
        for index, token in enumerate(raw_tokens)
        if (number := _parse_number_token(token)) is not None
    }
    education_constraints = _extract_education_constraints(normalized)

    lexical_items: list[str] = []
    for token in raw_tokens:
        canonical = canonicalize_lexical_term(token)
        if (
            token in _STOP_WORDS
            or not index_not_numeric(token)
            or not canonical
            or canonical in _QUERY_SCAFFOLDING_TERMS
        ):
            continue
        lexical_items.append(canonical)
```

### Explanation

Earlier, ordinary wording such as these could become hard CV requirements:

```text
knows
skilled
related
uses
worked
compare
versus
between
```

A CV naturally contains `Python`, `FastAPI`, or `PostgreSQL`, but it may not contain the literal word `knows`.

After the refactor:

```text
Who knows Python, FastAPI, and PostgreSQL?
```

is reduced to the actual factual requirements:

```text
python
fastapi
postgresql
```

This corrects the abstraction rather than hard-coding one question.

---

## Code excerpt 3 — Recover exact evidence without turning the scan into noisy search

**File:** `backend/app/cv_retrieval/assisted_retrieval.py`  
**Current lines:** 107–136

```python
supplemental: list[tuple[RawStoredChunk, CvEvidenceScore]] = []
for record in stored_chunks:
    if record.chunk_id in semantic_by_id:
        continue
    score = score_evidence_text(record.text, features)
    if features.has_numeric_constraints:
        # For numeric questions, the collection scan exists to
        # recover a relation-valid number that semantic top-k may
        # miss. Pure lexical overlap is not enough to add a new
        # chunk because it would recreate broad noisy retrieval.
        if score.numeric_score <= 0.0:
            continue
    elif score.lexical_score <= 0.0:
        continue
    supplemental.append((record, score))

supplemental.sort(
    key=lambda item: (
        item[1].contextual_numeric_match,
        item[1].numeric_score,
        item[1].lexical_score,
        item[1].combined_score,
        item[0].chunk_id,
    ),
    reverse=True,
)
for record, score in supplemental[
    : self._config.max_supplemental_hits
]:
    scored_candidates.append((None, record, score))
```

### Explanation

The exact scan is deliberately bounded.

For a numeric query, a chunk is not added merely because it contains the same number or shares some words. It must first earn a positive **relation-aware numeric score**.

This preserves the role of each technique:

- Chroma supplies broad semantic recall.
- The exact scan recovers precise evidence missed by semantic top-k.
- Relation-aware validation prevents the scan from adding large amounts of numeric noise.

---

## Code excerpt 4 — Require operator, value, and relationship in the same local context

**File:** `backend/app/cv_retrieval/evidence_analysis.py`  
**Current lines:** 920–976

```python
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
```

### Explanation

This is the most important evidence boundary.

A relation-bound number receives either:

- valid contextual proof; or
- zero numeric credit.

It does not receive partial credit simply because the number appears somewhere in the chunk.

For the exact-eight query:

```text
8 years of experience
```

gets:

```text
numeric_score = 0
```

while:

```text
managed 8 engineers
```

gets:

```text
numeric_score = 1
contextual_numeric_match = true
```

---

## Code excerpt 5 — Validate team size locally and reject duration numbers

**File:** `backend/app/cv_retrieval/evidence_analysis.py`  
**Current lines:** 979–1021

```python
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
```

### Explanation

The local windows have two purposes:

1. A wider local window checks for management context.
2. A very small count neighborhood binds the number to a nearby workforce noun.

That prevents this sentence from falsely satisfying an exact-eight query:

```text
Managed 6 engineers and delivered 8 projects.
```

The number `8` is not close to a workforce noun, so it cannot become team-size evidence.

---

## Code excerpt 6 — Combine semantic, lexical, and relation-aware numeric signals

**File:** `backend/app/cv_retrieval/evidence_analysis.py`  
**Current lines:** 575–606

```python
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
```

### Explanation

For numeric recruiter questions, exact relationship evidence is deliberately important.

The important design decision is not the precise coefficients. It is that the score components have distinct meanings:

```text
semantic score -> related meaning
lexical score  -> visible term coverage
numeric score  -> relation-valid numeric proof
```

The components remain exposed in diagnostics rather than being hidden behind one opaque score.

---

## Code excerpt 7 — Change the ranking unit from chunk to candidate

**File:** `backend/app/cv_retrieval/candidate_ranking.py`  
**Current lines:** 507–565

```python
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
```

### Explanation

Recruiter questions are about people, but vector databases return chunks.

Grouping by `candidate_id` allows:

- role evidence from one section;
- language evidence from another section;
- education evidence from another page;
- exact numeric evidence from a specific experience bullet;

to contribute to one candidate without mixing evidence between candidates.

---

## Code excerpt 8 — Rank candidates by requirement coverage and evidence quality

**File:** `backend/app/cv_retrieval/candidate_ranking.py`  
**Current lines:** 577–607

```python
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
```

### Explanation

Candidate ranking prioritizes:

1. **How many requested conditions the candidate satisfies**
2. **How strong the evidence is for those conditions**
3. **How much semantic support the candidate has**

Repeated chunks cannot repeatedly increase condition coverage because only the best evidence match supports each condition.

---

## Code excerpt 9 — Do not expose unsupported candidates to generation

**File:** `backend/app/cv_retrieval/final_retrieval.py`  
**Current lines:** 430–453

```python
def _select_support_pool(
    candidate_result: CandidateCvRetrievalResult,
    *,
    config: FinalRetrievalConfig,
) -> tuple[tuple[RankedCvCandidate, ...], FinalRetrievalOutcome]:
    complete = tuple(
        candidate
        for candidate in candidate_result.candidates
        if candidate.complete_condition_coverage
        and candidate.candidate_score >= config.complete_min_candidate_score
    )
    if complete:
        return complete, "supported"

    partial = tuple(
        candidate
        for candidate in candidate_result.candidates
        if candidate.matched_condition_count > 0
        and candidate.coverage_score >= config.partial_min_coverage
        and candidate.candidate_score >= config.partial_min_candidate_score
    )
    if partial:
        return partial, "partial"
    return (), "unsupported"
```

### Explanation

The hosted answer provider does not decide whether evidence exists.

The deterministic retrieval layer first returns one of:

```text
supported
partial
unsupported
```

An unsupported result contains no candidate evidence. This is why unsupported security-clearance questions remain local and deterministic instead of asking an LLM to improvise.

---

## Code excerpt 10 — Evaluate paraphrases without calling the hosted provider

**File:** `backend/app/cv_retrieval/robustness_evaluation.py`  
**Current lines:** 624–681

```python
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

return CvQueryRobustnessScenarioEvaluation(
    # ...
    passed=not failure_reasons,
    outcome=result.outcome,
    returned_candidate_ids=returned_ids,
    # ...
    hosted_provider_would_be_called=result.outcome != "unsupported",
    # ...
    failure_reasons=tuple(failure_reasons),
)
```

### Explanation

The evaluator checks more than the top candidate.

For every paraphrase it verifies:

- expected support outcome;
- expected candidate policy;
- source traceability;
- final context budget;
- parser output;
- condition coverage;
- whether a hosted provider would have been called.

It records the decision but does not make that provider call.

---

# 6. Test evidence to show

## Typed team-size interpretation

**File:** `backend/tests/test_cv_evidence_analysis.py`  
**Current lines:** 12–27

```python
def test_question_analysis_extracts_typed_team_size_constraint() -> None:
    """The number is modelled as team headcount, not as a loose token."""

    features = analyze_recruiter_question(
        "Who managed exactly eight engineers in a backend team?"
    )

    assert features.lexical_terms == ("manage", "engineer", "backend", "team")
    assert "backend team" in features.lexical_phrases
    assert len(features.numeric_constraints) == 1
    constraint = features.numeric_constraints[0]
    assert constraint.value == 8
    assert constraint.display_value == "8"
    assert constraint.operator == "eq"
    assert constraint.relation == "team_size"
    assert set(constraint.context_concepts) >= {"management", "workforce"}
```

## Adversarial negative contexts

**File:** `backend/tests/test_cv_evidence_analysis.py`  
**Current lines:** 86–113

```python
@pytest.mark.parametrize(
    "evidence",
    [
        "Senior engineer with 8 years of experience.",
        "Python 8y, PostgreSQL 7y and Docker 6y.",
        "Worked in backend engineering since 2018.",
        "Contact: +30 210 555 0188.",
        "Managed delivery projects for 8 years.",
        "Managed a platform team. Has 8 years of engineering experience.",
        "Managed 6 engineers and delivered 8 projects.",
        "Managed more than 8 engineers during a transformation programme.",
        "The organisation employed 8 engineers; this candidate was an individual contributor.",
    ],
)
def test_team_size_relation_rejects_unrelated_or_non_exact_numbers(
    evidence: str,
) -> None:
    """Durations, dates, phones and unrelated counts cannot become headcount."""

    features = analyze_recruiter_question(
        "Who managed exactly eight engineers?"
    )
    score = score_evidence_text(evidence, features, semantic_score=0.9)

    assert score.numeric_score == 0.0
    assert score.contextual_numeric_match is False
```

## Scaffolding regression

**File:** `backend/tests/test_cv_query_understanding.py`  
**Current lines:** 19–46

```python
@pytest.mark.parametrize(
    "question, expected_terms",
    [
        (
            "Who knows Python, FastAPI, and PostgreSQL?",
            ("python", "fastapi", "postgresql"),
        ),
        (
            "Find people skilled in Python, FastAPI, and PostgreSQL.",
            ("python", "fastapi", "postgresql"),
        ),
        (
            "Which candidate combines PyTorch, NLP, and vector databases?",
            ("pytorch", "nlp", "vector", "database"),
        ),
    ],
)
def test_conversational_scaffolding_never_becomes_evidence(
    question: str,
    expected_terms: tuple[str, ...],
) -> None:
    features = analyze_recruiter_question(question)

    assert features.lexical_terms == expected_terms
```

## Negative controls in the matrix

The committed matrix contains:

- 13 query families;
- 50 total scenarios;
- exact candidate expectations for focused queries;
- subset policies for broad queries;
- unsupported `none` policies for facts absent from the corpus.

The two important unsupported families are:

```text
exactly three years of professional experience
government security clearance
```

These protect the system from solving false negatives by becoming too permissive.

---

# 7. Measurable before-and-after result

## Baseline

```text
Families: 12
Scenarios: 48
Passed: 18
Failed: 30
Hosted provider calls made: 0
```

The diagnostic report exposed reusable failure categories:

- conversational scaffolding promoted to evidence;
- degree aliases and field binding;
- numeric comparison wording;
- native-language idioms;
- engineer/developer role morphology;
- candidate comparison wording;
- incidental versus candidate-owned evidence.

## Final regression result

```text
Families: 13
Scenarios: 50
Passed: 50
Failed: 0
Inconsistent outcomes: 0 families
Hosted provider calls made: 0
Result: PASS
```

Two broad query families can produce small variations in their valid top-10 result set because more qualifying candidates exist than the result limit. Exact-policy families remain candidate-set consistent.

## Strict evaluation command

```powershell
docker compose exec backend python -m app.scripts.evaluate_cv_query_robustness `
    --strict `
    --json-output data/cv_query_robustness_after_refactor.json
```

---

# 8. Recommended video walkthrough

The following sequence is designed for the technical-highlight section of the final delivery video.

## Step 1 — Introduce the challenge

### Show

The final application or a slide containing:

```text
Who managed exactly eight engineers?
```

### Explain

> Semantic retrieval is good at finding related text, but related text is not always sufficient proof. During live inspection, the system could confuse eight years of experience with a request for exactly eight engineers managed.

---

## Step 2 — Show the incorrect and correct evidence

### Show

```text
Incorrect:
Senior Python backend engineer with 8 years of experience...

Correct:
Team leadership: managed 8 people.
Led a team of exactly 8 engineers...
```

### Explain

> Both chunks are related to engineering seniority, but only the second chunk proves the team-size relationship.

---

## Step 3 — Show typed query interpretation

### Open

```text
backend/app/cv_retrieval/evidence_analysis.py
```

### Show

- `NumericQueryConstraint`
- the `operator` and `relation` fields;
- the scaffolding filter in `analyze_recruiter_question`.

### Explain

> The system models the question as a typed requirement: equality, value eight, relation team size. It also removes recruiter framing such as “who knows” or “find people skilled in” from the actual evidence conditions.

---

## Step 4 — Show clause-local evidence validation

### Show

- `_score_numeric_constraint`
- `_matches_team_size_relation`

### Explain

> The number, operator, management action, and workforce target must be valid in the same local clause or token window. A duration, date, phone fragment, project count, or unrelated number receives zero team-size credit.

Use this short phrase:

> The application does not ask only, “Is the number present?” It asks, “What does this number mean here?”

---

## Step 5 — Show hybrid retrieval and candidate aggregation

### Open

```text
backend/app/cv_retrieval/assisted_retrieval.py
backend/app/cv_retrieval/candidate_ranking.py
```

### Show

- the bounded supplemental exact scan;
- grouping by `candidate_id`;
- the candidate score based on coverage, evidence quality, and semantic support.

### Explain

> Chroma remains responsible for semantic recall. The bounded scan recovers relation-valid evidence that top-k may miss. Chunks are then grouped by candidate so facts from different CV sections can support the same person without crossing candidate boundaries.

---

## Step 6 — Demonstrate the corrected application

### Ask

```text
Who managed exactly eight engineers?
```

### Show

- correct candidate ranking;
- grounded evidence;
- page/source citation.

Then ask:

```text
Find a backend engineer who speaks German natively.
```

### Explain

> The same approach also handles compound relations. Backend profession and German native proficiency must both belong to the same candidate, even when they appear in different CV sections.

---

## Step 7 — Show that the solution generalized

### Run or display

```powershell
docker compose exec backend python -m app.scripts.evaluate_cv_query_robustness --strict
```

### Highlight

```text
50 passed
0 failed
0 hosted-provider calls
```

### Explain

> The evaluator runs paraphrase families through the real retrieval pipeline without paying for answer generation. It records parser conditions, candidate coverage, source traceability, context budgets, and expected outcomes.

---

## Step 8 — Show negative controls

### Ask

```text
Who has exactly 3 years of professional experience?
```

and:

```text
Which candidates hold government security clearance?
```

### Explain

> Improving recall was not accepted unless unsupported claims remained unsupported. These questions return no candidates and do not call the hosted answer provider.

---

# 9. Concise narration

The following paragraph can be used as the opening or closing summary of the technical-highlight section:

> The technical part I am most proud of is the evidence-verification layer between vector retrieval and answer generation. During live testing, I found that semantic similarity could retrieve related CV text but could not prove exact relationships. A candidate with eight years of experience could appear relevant to a question asking who managed eight engineers. I introduced typed query constraints, clause-local evidence validation, comparison-operator handling, and candidate-level evidence aggregation. Embeddings remain responsible for broad recall, while deterministic Python verifies that a number, skill, role, language, or qualification belongs to the requested relationship and to the same candidate. I then added a provider-free robustness evaluator with paraphrase families and negative controls. The initial baseline passed 18 of 48 scenarios; after the refactor, the expanded matrix passed all 50 scenarios while unsupported claims remained unsupported.

---

# 10. Closing takeaway

The distinctive engineering decision was not to replace embeddings with exact filtering and not to let an LLM decide whether evidence exists.

Instead, the application gives each layer a clear responsibility:

```text
Embeddings retrieve meaning.
Deterministic code verifies facts and relationships.
Candidate aggregation preserves ownership.
Support thresholds prevent unsupported generation.
The LLM explains only grounded evidence.
```

That combination makes the retrieval system more accurate, explainable, testable, and safe than a generic nearest-neighbour RAG prototype.
