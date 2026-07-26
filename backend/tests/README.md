# Backend test architecture

## Summary explanation

The test suite validates each pipeline stage independently and then checks the
connections between stages. The tests are not one large end-to-end script. They
use focused fixtures and test doubles so failures identify the exact layer that
broke.

```text
schema tests
-> generation tests
-> portrait/rendering tests
-> ingestion/storage tests
-> retrieval tests
-> answer/citation tests
-> API tests
-> CLI/help/setup tests
```

The confirmed full Docker baseline is **369 passed**.

## Position in the application workflow

Tests consume the same public functions, models and service boundaries used by
scripts and API routes. Hosted calls are replaced with deterministic fakes where
possible, so most correctness checks do not require API keys or network access.

## Main shared files

| File | Purpose |
|---|---|
| [`conftest.py`](conftest.py) | Provides fresh valid candidate payloads and portrait-plan fixtures used across schema and generation tests. |
| [`cv_retrieval_test_helpers.py`](cv_retrieval_test_helpers.py) | Builds deterministic candidate/evidence results for final retrieval and answer tests. |
| [`pytest.ini`](../pytest.ini) | Defines test discovery and Python path behavior. |

## Test execution order conceptually

Pytest itself may collect files in its own order. The useful architectural order
for reading the suite is below.

### 1. Candidate schema and plan

```text
test_candidate_schemas.py
-> nested CandidateProfile validation

test_candidate_dataset_plan.py
-> committed plan structure and consistency

test_candidate_generation_plan.py
-> slot selection rules
```

### 2. Candidate generation

```text
test_candidate_generation_prompt.py
-> prompt contains locked slot facts

test_openai_candidate_generator.py
-> provider contract and structured parsing

test_candidate_experience.py
-> deterministic timeline arithmetic

test_candidate_generation_compliance.py
-> profile satisfies the selected slot

test_candidate_profile_uniqueness.py
-> cross-profile duplicate protection

test_candidate_generation_service.py
-> retry and correction loop

test_candidate_profile_persistence.py
-> sorted and safe JSON storage

test_candidate_dataset_validation.py
-> complete collection and scenario checks
```

### 3. Portrait and rendering

```text
test_candidate_portrait_plan.py
-> profile/portrait coverage

test_portrait_generation_planning.py
-> deterministic image jobs

test_portrait_generation_images.py
-> decode, crop, resize and WebP inspection

test_openai_portrait_generator.py
-> provider boundary

test_portrait_generation_service.py
-> retries and accepted image result

test_cv_rendering_*.py
-> formatting, planning and HTML/PDF rendering

test_cv_pdf_validation.py
-> extracted PDF facts and collection scenarios
```

### 4. Ingestion and vector storage

```text
test_cv_ingestion_loading.py
-> file hashing, extraction and metadata detection

test_cv_chunking.py
-> section-aware chunks, limits, overlap and stable IDs

test_cv_embeddings.py
-> vector count, dimension and normalisation

test_cv_chroma_store.py
-> collection compatibility, persistence and query behavior

test_cv_ingestion_service.py
-> skip, refresh, replace, partial recovery and summary flow

test_cv_ingestion_naming.py
-> readable filename planning without identity changes
```

### 5. Retrieval

```text
test_cv_raw_retrieval.py
-> broad semantic search contract

test_cv_query_understanding.py
-> parsed text, education and numeric conditions

test_cv_evidence_analysis.py
-> relation-aware exact evidence scoring

test_cv_assisted_retrieval.py
-> semantic + supplemental exact evidence

test_cv_candidate_ranking.py
-> candidate grouping, coverage and evidence selection

test_cv_candidate_retrieval.py
-> candidate-aware coordinator

test_cv_final_retrieval.py
-> supported/partial/unsupported policy and context budgets

test_cv_retrieval_evaluation.py
-> planned search scenarios

test_cv_query_robustness_evaluation.py
-> paraphrase families and parser diagnostics
```

### 6. Grounded answers and citations

```text
test_cv_grounded_answer_provider_selection.py
-> auto/OpenAI/Gemini/deterministic resolution

test_openai_grounded_answer_provider.py
+ test_gemini_grounded_answer_provider.py
-> hosted structured-draft contracts

test_cv_grounded_answer_prompt.py
-> only approved context and source IDs enter the prompt

test_cv_grounded_answer_sources.py
-> stable source IDs and candidate ownership

test_cv_grounded_answer_generation.py
-> unsupported, deterministic, hosted retry and draft validation flows
```

### 7. Services and API

```text
test_candidate_catalog_service.py
-> index-backed catalogue and trusted PDF resolution

test_api_health.py
-> provider/index readiness

test_api_candidates.py
-> candidate list and PDF endpoint

test_api_chat.py
-> public chat response and safe failures

test_api_cors.py
-> browser origin boundary

test_api_openapi.py
-> public schema and examples
```

### 8. Commands, help and setup

CLI tests call each script's `run_cli()` with fakes or temporary paths. They
validate argument combinations, exit codes, output summaries and side effects.

`test_script_help_reference.py` discovers runnable script modules and requires
all of them to have complete help documentation and central README coverage.

`test_local_setup_script.py` validates root/backend Bash and PowerShell setup
help, safe unknown-argument handling and no environment-file changes during
help output.

## Important shared helpers

### `valid_candidate_payload`

A function-scoped fixture returning a new valid dictionary per test. Tests can
mutate it without affecting another test.

### `valid_candidate_001_payload` and `valid_candidate_002_payload`

Profiles designed to exercise controlled slot compliance and deterministic
experience normalisation.

### `portrait_plan_factory`

Creates compact plan fixtures for portrait coverage tests.

### `CandidateSpec`

A small declarative input for retrieval tests: candidate identity, match count,
score, coverage and evidence text.

### `build_candidate_result(specs, ...)`

Builds a complete deterministic `CandidateCvRetrievalResult` without Chroma or
an embedding model. Final retrieval tests can therefore focus on support policy
and context budgeting.

### `finalize_for_test(...)`

Calls the production `finalize_candidate_retrieval()` function with a synthetic
candidate result.

## Test-double pattern

Production code uses small protocols and injectable dependencies:

```text
CandidateProfileProvider
PortraitImageProvider
QueryEmbeddingProvider
RawVectorRepository
ExactEvidenceRepository
GroundedAnswerProvider
```

Tests implement only the methods required by the layer under test. This avoids
network calls while still exercising the production coordinator.

## Temporary data pattern

Filesystem and Chroma tests use Pytest temporary directories. They verify real
read/write behavior without touching project data or the persisted developer
index.

## Running tests

Full backend suite:

```powershell
docker compose -p ai-cv-screener-openai exec backend pytest
```

One file:

```powershell
docker compose -p ai-cv-screener-openai exec backend `
  pytest tests/test_cv_ingestion_service.py -q
```

One test by name:

```powershell
docker compose -p ai-cv-screener-openai exec backend `
  pytest tests/test_cv_final_retrieval.py -k unsupported -q
```

## How to follow a failing test into production code

Example:

```text
test_cv_ingestion_service.py fails
-> open the specific test and fixture
-> identify the called CvIngestionService.ingest() branch
-> follow into extraction/chunking/repository function named in the assertion
```

The section READMEs beside production code describe the exact runtime order for
that layer.
