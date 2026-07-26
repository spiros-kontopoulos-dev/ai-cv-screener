# Candidate-aware CV retrieval pipeline

## Summary explanation

This section turns a recruiter question into ranked candidate evidence. It does
not stop at the nearest vector chunks. It combines semantic recall with exact
text and numeric evidence, groups chunks by candidate, measures requirement
coverage and creates a bounded result for answer generation.

The central design rule is:

> Chunks are evidence units. Candidates are ranking units.

## Position in the complete application

### State before this section

- the Chroma collection contains complete PDF-derived chunks and vectors;
- every chunk has candidate, document, page and section metadata;
- the recruiter question is plain text;
- no answer provider should be called yet.

### State after this section

- the question has explicit parsed requirements where possible;
- evidence chunks are scored for semantic and exact support;
- chunks are grouped into whole candidates;
- candidates have condition coverage and candidate scores;
- the result is classified as `supported`, `partial` or `unsupported`;
- only a small source-backed context is available to answer generation.

```text
Recruiter question
-> raw semantic retrieval
-> query feature analysis
-> exact evidence recovery
-> candidate conditions
-> candidate grouping and ranking
-> support classification
-> evidence/context budgeting
-> FinalCvRetrievalResult
```

## Actual entry point and builder chain

The public retrieval object is built by:

```text
build_final_cv_retriever(settings)
```

Its nested dependency chain is:

```text
FinalCvRetriever
└── CandidateAwareCvRetriever
    └── AssistedCvRetriever
        ├── RawCvRetriever
        └── CvChromaRepository exact-evidence reader
```

For a normal question, answer generation calls:

```text
FinalCvRetriever.retrieve(FinalCvRetrievalQuery(...))
```

## Exact runtime order

### Stage 1 — raw semantic retrieval

```text
RawCvRetriever.retrieve()
-> validate question length and requested result limit
-> verify Chroma collection compatibility and non-empty state
-> embedding_provider.embed_texts((question,))
-> vector_repository.query_nearest(query_vector)
-> convert Chroma matches to typed RawCvRetrievalHit objects
-> return RawCvRetrievalResult in distance order
```

This stage is intentionally broad. It finds related chunks but does not yet
prove exact requirements or rank whole candidates.

### Stage 2 — assisted exact-evidence retrieval

```text
AssistedCvRetriever.retrieve()
-> run RawCvRetriever.retrieve()
-> analyze_recruiter_question(question)
-> score every semantic hit with score_raw_hit()
-> scan stored chunk text for bounded exact evidence
-> score exact matches with score_evidence_text()
-> reject numeric chunks that do not prove the required relation
-> deduplicate semantic and supplemental hits
-> sort the combined evidence pool
-> return AssistedCvRetrievalResult
```

The supplemental scan exists because vector top-k can miss an exact name,
number, degree phrase or language term even when that fact is decisive.

### Stage 3 — candidate-aware grouping and ranking

```text
CandidateAwareCvRetriever.retrieve()
-> resolve candidate and evidence limits
-> call AssistedCvRetriever.retrieve()
-> rank_candidates()
   -> build_candidate_conditions(query features)
   -> group hits by candidate_id
   -> score every condition against each candidate's evidence
   -> calculate matched-condition count and coverage
   -> calculate candidate score
   -> select a balanced evidence set per candidate
   -> sort candidates
-> return CandidateCvRetrievalResult
```

A candidate may satisfy one request with several chunks: for example one chunk
for Python, one for PostgreSQL and one for a language requirement.

### Stage 4 — final support and context policy

```text
FinalCvRetriever.retrieve()
-> request a larger candidate pool from CandidateAwareCvRetriever
-> finalize_candidate_retrieval()
   -> _select_support_pool()
   -> prefer complete matches above complete score threshold
   -> otherwise allow only configured high-confidence partial matches
   -> otherwise return unsupported
   -> _budget_candidates()
   -> limit candidates, chunks, excerpt length and total context characters
-> return FinalCvRetrievalResult
```

The answer provider receives only `FinalCvRetrievalResult.context_text` and the
matching structured source objects, not the complete vector store.

## File map in execution order

| Runtime phase | File | Responsibility |
|---:|---|---|
| 1 | [`models.py`](models.py) | Defines validated contracts for the raw semantic stage and source metadata. |
| 2 | [`raw_retrieval.py`](raw_retrieval.py) | Embeds the question and retrieves broad nearest-neighbour chunks from Chroma. |
| 3 | [`evidence_analysis.py`](evidence_analysis.py) | Parses text, phrase, education and numeric constraints and scores chunk evidence. |
| 4 | [`assisted_retrieval.py`](assisted_retrieval.py) | Combines semantic hits with bounded exact-text recovery and deduplication. |
| 5 | [`candidate_ranking.py`](candidate_ranking.py) | Builds query conditions, groups evidence by candidate and calculates coverage/ranking. |
| 6 | [`candidate_retrieval.py`](candidate_retrieval.py) | Coordinates assisted retrieval and candidate ranking with configured limits. |
| 7 | [`final_retrieval.py`](final_retrieval.py) | Applies support thresholds and builds the bounded prompt-ready context. |
| Diagnostic | [`evaluation.py`](evaluation.py) | Runs final retrieval against planned corpus search scenarios. |
| Diagnostic | [`robustness_evaluation.py`](robustness_evaluation.py) | Runs paraphrase families and exposes parser and candidate-coverage diagnostics. |

## Important functions and classes

### `RawCvRetriever.retrieve(query)`

The broad recall stage. It validates:

- question length;
- collection availability;
- collection compatibility;
- embedding output;
- persisted source metadata.

It returns chunk-level hits in Chroma distance order.

### `analyze_recruiter_question(text)`

Creates `CvQueryEvidenceFeatures`. It extracts or normalises:

- important lexical phrases;
- text relations such as roles and languages;
- degree and education constraints;
- numeric comparisons and operators;
- local concepts connected to each number.

It is deterministic and provider-free.

### `score_raw_hit(hit, features)`

Combines semantic relevance derived from Chroma distance with exact evidence
signals. It keeps diagnostics explaining why a chunk is useful.

### `score_evidence_text(text, features)`

Scores a stored chunk during exact recovery. Numeric checks are relation-aware.
For example:

```text
question: managed 8 engineers
```

A chunk mentioning `8 years of experience` cannot satisfy the team-size
condition because the local relation is wrong.

Important helpers include:

- `_build_numeric_constraint()`;
- `_score_numeric_constraint()`;
- `_matches_team_size_relation()`;
- `_matches_experience_duration_relation()`;
- `_extract_education_constraints()`;
- `_match_text_relation()`.

### `AssistedCvRetriever.retrieve(query)`

Coordinates semantic and exact retrieval. It keeps the semantic pool as the
main recall source, scans the stored chunks for strong supplemental evidence,
removes duplicate chunk IDs and limits the number of supplemental hits.

### `build_candidate_conditions(features)`

Converts parsed query features into explicit `CandidateQueryCondition` objects.
Conditions are the requirements used to calculate candidate coverage.

Examples:

- skill or technology phrase;
- professional role/domain phrase;
- language and proficiency;
- education degree or field;
- numeric experience threshold;
- team-size relation.

### `rank_candidates(assisted_result, candidate_limit, evidence_limit)`

The main candidate-level algorithm:

```text
query conditions + scored chunks
-> group chunks by candidate ID
-> best match for each condition
-> coverage score
-> candidate score
-> selected candidate evidence
-> stable ranked list
```

Candidate identity is validated so chunks from different candidates cannot be
combined into one result.

### `CandidateAwareCvRetriever.retrieve(query)`

Small orchestration class that resolves limits, calls assisted retrieval and
passes the result into `rank_candidates()`.

### `finalize_candidate_retrieval(...)`

Converts ranked candidates into an answer-safe result. It makes the final
policy decision:

- **supported** — at least one candidate has complete condition coverage and passes the complete score threshold;
- **partial** — no complete candidate exists, but one or more candidates pass the configured partial coverage and score thresholds;
- **unsupported** — available evidence is too weak or incomplete.

### `_budget_candidates(...)`

Builds the exact context that can be sent to answer generation. It limits:

- final candidate count;
- evidence chunks per candidate;
- total evidence chunks;
- text characters per excerpt;
- total context characters.

Evidence is prioritised by condition support so a lower-value duplicate chunk
does not displace a chunk that proves a missing requirement.

## Main data contracts

```text
RawCvRetrievalQuery
-> RawCvRetrievalResult
-> AssistedCvRetrievalResult
-> CandidateCvRetrievalResult
-> FinalCvRetrievalResult
```

`FinalCvRetrievalResult` contains:

- original question;
- outcome and support message;
- final candidates;
- source-labelled evidence;
- candidate and context limits;
- prompt-ready context text;
- budget-exhaustion state.

## Supported, partial and unsupported examples

### Complete support

```text
Question requires Python + FastAPI + PostgreSQL
-> candidate has evidence for all three conditions
-> candidate passes complete score threshold
-> supported
```

### Partial support

```text
Question requires Python + a specific degree
-> candidate has strong Python evidence but not the degree
-> coverage and score pass partial policy
-> partial, with the missing requirement made explicit
```

### Unsupported

```text
Question asks for a fact not present in indexed CV evidence
-> semantic similarity may still return related chunks
-> no candidate passes support policy
-> unsupported with no exposed candidates
```

## Why the pipeline is split into stages

- raw semantic search optimises recall;
- evidence analysis proves exact facts and relationships;
- assisted retrieval recovers missed decisive chunks;
- candidate ranking joins evidence that belongs to the same person;
- final retrieval applies answer-safety policy and context budgets.

Keeping these stages separate makes failures inspectable. The project includes a
CLI for each stage so a developer can see where a question changes from good to
bad.

## Connection to the next section

```text
FinalCvRetrievalResult
-> cv_answer_generation.GroundedCvAnswerGenerator.generate()
-> deterministic or hosted wording
-> candidate-owned citation validation
```

## Main inspection commands

```powershell
docker compose -p ai-cv-screener-openai exec backend `
  python -m app.scripts.inspect_raw_cv_retrieval --help

docker compose -p ai-cv-screener-openai exec backend `
  python -m app.scripts.inspect_assisted_cv_retrieval --help

docker compose -p ai-cv-screener-openai exec backend `
  python -m app.scripts.inspect_candidate_cv_retrieval --help

docker compose -p ai-cv-screener-openai exec backend `
  python -m app.scripts.inspect_final_cv_retrieval --help

docker compose -p ai-cv-screener-openai exec backend `
  python -m app.scripts.evaluate_cv_query_robustness --help
```

## Related tests

- `test_cv_raw_retrieval.py`
- `test_cv_query_understanding.py`
- `test_cv_evidence_analysis.py`
- `test_cv_assisted_retrieval.py`
- `test_cv_candidate_ranking.py`
- `test_cv_candidate_retrieval.py`
- `test_cv_final_retrieval.py`
- `test_cv_retrieval_evaluation.py`
- `test_cv_query_robustness_evaluation.py`
- retrieval inspection CLI tests
