# Backend script command reference

## Summary

The modules in this directory are developer-facing commands for building,
checking, and inspecting the AI CV Screener data pipeline. Every runnable
script supports `--help` and prints:

- its purpose;
- every available argument;
- valid argument combinations;
- whether it reads data, writes files, changes Chroma, or calls a provider;
- practical examples.

Run commands from the backend container:

```powershell
docker compose -p ai-cv-screener-openai exec backend `
  python -m app.scripts.<script_name> --help
```

The shorter `python -m ...` form shown below is the part executed inside the
container.

## Quick safety guide

| Command type | Reads data | Writes files | Changes Chroma | Hosted provider call |
|---|---:|---:|---:|---:|
| `inspect_*` except grounded answers | Yes | No | No | No |
| `validate_*` | Yes | No | No | No |
| `smoke_test_cv_index` | Yes | No | No | No |
| `evaluate_cv_query_robustness` | Yes | Optional JSON report | No | No |
| `generate_candidate_profiles` | Yes | Yes | No | OpenAI |
| `generate_candidate_portraits` | Yes | Yes | No | OpenAI image provider |
| `render_candidate_cvs` | Yes | Yes | No | No |
| `rename_cv_documents --apply` | Yes | Renames PDFs | No | No |
| `ingest_cv_documents` | Yes | Chroma storage | Yes | No |
| `inspect_grounded_cv_answer` | Yes | No | No | Depends on provider mode |

## Candidate profile generation

### `generate_candidate_profiles`

Creates validated fictional profiles from the controlled dataset plan.

Selection modes—choose exactly one:

```powershell
python -m app.scripts.generate_candidate_profiles --candidate-id candidate_003
python -m app.scripts.generate_candidate_profiles --count 3
python -m app.scripts.generate_candidate_profiles --all
```

Selection modifiers:

```powershell
# Start count/all selection from a particular slot.
python -m app.scripts.generate_candidate_profiles `
  --count 5 --start-from candidate_011

# Preview selection and validation without OpenAI or file changes.
python -m app.scripts.generate_candidate_profiles --all --dry-run

# Keep existing profiles and generate only missing selected IDs.
python -m app.scripts.generate_candidate_profiles --all --resume

# Replace the saved collection with this command's selected profiles.
python -m app.scripts.generate_candidate_profiles --all --overwrite

# Print newly accepted profiles as formatted JSON as well as saving them.
python -m app.scripts.generate_candidate_profiles `
  --candidate-id candidate_003 --print-json
```

Rules:

- `--candidate-id`, `--count`, and `--all` are mutually exclusive.
- `--start-from` works with `--count` or `--all`, not `--candidate-id`.
- `--resume` and `--overwrite` are mutually exclusive.
- `--dry-run` makes no provider call and writes nothing.

### `validate_candidate_profiles`

Validates the complete saved collection against plan slots, distributions,
search scenarios, experience arithmetic, and uniqueness rules.

```powershell
python -m app.scripts.validate_candidate_profiles
```

This command takes no filters and writes nothing.

### `validate_candidate_schema`

Demonstrates the Pydantic boundary with one valid in-memory payload and one
intentionally invalid payload.

```powershell
python -m app.scripts.validate_candidate_schema
```

This command takes no arguments and writes nothing.

## Portrait generation

### `generate_candidate_portraits`

Creates planned fictional portraits and normalizes them to deterministic WebP
assets.

Selection modes—choose exactly one:

```powershell
python -m app.scripts.generate_candidate_portraits `
  --candidate-id candidate_003
python -m app.scripts.generate_candidate_portraits --count 3
python -m app.scripts.generate_candidate_portraits --all
```

Useful combinations:

```powershell
# Preview paths without a provider call.
python -m app.scripts.generate_candidate_portraits --all --dry-run

# Preview the complete prompts as well.
python -m app.scripts.generate_candidate_portraits `
  --candidate-id candidate_003 --dry-run --show-prompts

# Start a count/all selection from a particular candidate.
python -m app.scripts.generate_candidate_portraits `
  --count 5 --start-from candidate_011

# Replace an existing valid portrait after visual review.
python -m app.scripts.generate_candidate_portraits `
  --candidate-id candidate_003 --overwrite
```

Rules:

- `--candidate-id`, `--count`, and `--all` are mutually exclusive.
- `--start-from` works only with `--count` or `--all`.
- Normal runs may call the configured image provider and write WebP files.
- `--dry-run` writes nothing.

### `validate_candidate_portraits`

Checks portrait-plan coverage, dimensions, format, missing images, invalid
images, and unexpected files.

```powershell
python -m app.scripts.validate_candidate_portraits
```

This command takes no filters and writes nothing.

## CV rendering and PDF checks

### `render_candidate_cvs`

Renders validated profiles through Jinja and WeasyPrint.

Selection modes—choose exactly one:

```powershell
python -m app.scripts.render_candidate_cvs `
  --candidate-id candidate_003
python -m app.scripts.render_candidate_cvs --count 3
python -m app.scripts.render_candidate_cvs --all
```

Useful combinations:

```powershell
# Inspect planned source and output paths without writing files.
python -m app.scripts.render_candidate_cvs --all --dry-run

# Render and retain browser-inspectable HTML beside the PDF.
python -m app.scripts.render_candidate_cvs --count 3 --keep-html

# Require every portrait-planned candidate to have a valid portrait.
python -m app.scripts.render_candidate_cvs `
  --all --enforce-portrait-plan

# Render a range beginning at a selected candidate.
python -m app.scripts.render_candidate_cvs `
  --count 5 --start-from candidate_011
```

Rules:

- `--candidate-id`, `--count`, and `--all` are mutually exclusive.
- `--start-from` works only with `--count` or `--all`.
- `--keep-html` cannot be combined with `--dry-run` because it writes a file.
- Normal runs write PDFs and optionally HTML previews.

### `validate_candidate_cvs`

Validates the full rendered PDF collection for file count, readable text,
expected facts, page limits, and planned search scenarios.

```powershell
python -m app.scripts.validate_candidate_cvs
```

This command takes no filters and writes nothing.

### `rename_cv_documents`

Builds readable names from text extracted from each PDF. Preview is the default.

Select PDFs in one of three ways:

```powershell
python -m app.scripts.rename_cv_documents --file data/cv_pdfs/example.pdf
python -m app.scripts.rename_cv_documents --directory data/cv_pdfs
python -m app.scripts.rename_cv_documents --all
```

Additional combinations:

```powershell
# Include nested folders.
python -m app.scripts.rename_cv_documents `
  --directory data/imports --recursive

# Perform the displayed renames.
python -m app.scripts.rename_cv_documents --all --apply
```

Rules:

- `--file`, `--directory`, and `--all` are mutually exclusive.
- Repeat `--file` to select several individual PDFs.
- Without `--apply`, nothing changes.
- Renaming a PDF does not automatically rebuild the vector index. Document
  identity remains hash-based, but re-ingest when stored source metadata should
  show the new filename.

## PDF extraction, chunking, and embeddings

The three inspection commands below use the same selection rules:

- choose one of repeated `--file`, one `--directory`, or `--all`;
- add `--recursive` to `--directory` or `--all` when nested PDFs are needed;
- inspection happens in memory and writes no vector records.

### `inspect_cv_documents`

Shows SHA-256 identity, detected candidate metadata, page text, and extraction
warnings before chunking.

```powershell
python -m app.scripts.inspect_cv_documents `
  --file data/cv_pdfs/example.pdf
python -m app.scripts.inspect_cv_documents --directory data/cv_pdfs
python -m app.scripts.inspect_cv_documents `
  --all --recursive --preview-characters 400
```

Candidate metadata overrides may be supplied only when exactly one PDF is
selected:

```powershell
python -m app.scripts.inspect_cv_documents `
  --file data/imports/cv.pdf `
  --candidate-id candidate_031 `
  --candidate-name "Alex Morgan" `
  --professional-title "Python Engineer"
```

### `inspect_cv_chunks`

Runs extraction and section-aware chunking without embeddings or Chroma writes.

```powershell
python -m app.scripts.inspect_cv_chunks `
  --file data/cv_pdfs/example.pdf
python -m app.scripts.inspect_cv_chunks --file first.pdf --file second.pdf
python -m app.scripts.inspect_cv_chunks --directory data/cv_pdfs --recursive
```

Temporary chunk-setting overrides can be combined with any selection:

```powershell
python -m app.scripts.inspect_cv_chunks `
  --all `
  --chunking-version cv-sections-experiment `
  --max-characters 1200 `
  --min-characters 350 `
  --overlap-characters 120 `
  --preview-characters 300
```

These overrides inspect an alternative result in memory. They do not update
application settings or Chroma.

### `inspect_cv_embeddings`

Runs extraction, chunking, and local embedding generation without storing
vectors.

```powershell
python -m app.scripts.inspect_cv_embeddings `
  --file data/cv_pdfs/example.pdf --limit-chunks 5
python -m app.scripts.inspect_cv_embeddings `
  --all --limit-chunks 10 --preview-vectors 3
```

`--limit-chunks` is useful for a quick model/dimension/norm smoke test.

## Vector-index operations

### `ingest_cv_documents`

Runs PDF selection, extraction, chunking, local embeddings, and persistent
Chroma storage.

Selection modes—choose exactly one:

```powershell
# One or several explicit files.
python -m app.scripts.ingest_cv_documents `
  --file data/cv_pdfs/example.pdf
python -m app.scripts.ingest_cv_documents `
  --file first.pdf --file second.pdf

# One directory, optionally recursive.
python -m app.scripts.ingest_cv_documents `
  --directory data/cv_pdfs
python -m app.scripts.ingest_cv_documents `
  --directory data/imports --recursive

# The configured default CV directory.
python -m app.scripts.ingest_cv_documents --all
python -m app.scripts.ingest_cv_documents --all --recursive
```

Index-changing modes:

```powershell
# Delete the complete configured collection, then ingest the selection.
python -m app.scripts.ingest_cv_documents --all --rebuild

# Replace older revisions for selected source paths or candidate IDs.
python -m app.scripts.ingest_cv_documents `
  --file data/cv_pdfs/updated.pdf --replace-existing
```

Single-PDF metadata overrides:

```powershell
python -m app.scripts.ingest_cv_documents `
  --file data/imports/cv.pdf `
  --candidate-id candidate_031 `
  --candidate-name "Alex Morgan" `
  --professional-title "Python Engineer"
```

Rules:

- `--file`, `--directory`, and `--all` are mutually exclusive.
- Metadata overrides require exactly one selected PDF.
- `--rebuild` deletes the complete collection before ingestion.
- `--replace-existing` removes older candidate/source revisions before storing
  the selected document.
- Unchanged complete documents are skipped by normal idempotent ingestion.

### `inspect_cv_vector_store`

Shows collection compatibility metadata and document/candidate coverage.

```powershell
python -m app.scripts.inspect_cv_vector_store
```

This command takes no arguments and writes nothing.

### `smoke_test_cv_index`

Queries raw nearest Chroma chunks. It bypasses exact evidence, candidate
ranking, support classification, and answer generation.

```powershell
python -m app.scripts.smoke_test_cv_index --query "Python FastAPI"
python -m app.scripts.smoke_test_cv_index `
  --query "Python" --query "German" --top-k 10
```

`--preview-characters` changes only the printed snippet length.

## Retrieval inspection

These commands are ordered from the earliest retrieval stage to the final
supported-evidence boundary. They read Chroma and write nothing.

### `inspect_raw_cv_retrieval`

Shows broad semantic chunk recall only.

```powershell
python -m app.scripts.inspect_raw_cv_retrieval `
  --query "Python backend engineer"
python -m app.scripts.inspect_raw_cv_retrieval `
  --query "German native speaker" --top-k 20
```

`--result-limit` and `--top-k` are aliases.

### `inspect_assisted_cv_retrieval`

Adds exact lexical and relation-aware numeric evidence to semantic recall.

```powershell
python -m app.scripts.inspect_assisted_cv_retrieval `
  --query "Who has 5 years of Python?" `
  --top-k 40 --display-limit 10
```

### `inspect_candidate_cv_retrieval`

Shows chunk grouping, hard-condition coverage, candidate scores, and bounded
candidate-owned evidence.

```powershell
python -m app.scripts.inspect_candidate_cv_retrieval `
  --query "Who knows Python and PostgreSQL?"
python -m app.scripts.inspect_candidate_cv_retrieval `
  --query "Who managed 8 engineers?" `
  --raw-limit 50 `
  --candidate-limit 5 `
  --evidence-limit 4
```

`--semantic-result-limit` and `--raw-limit` are aliases.

### `inspect_final_cv_retrieval`

Shows supported/partial/unsupported classification and the final bounded
prompt-ready context. It does not call an answer provider.

```powershell
python -m app.scripts.inspect_final_cv_retrieval `
  --query "Who has more than 5 years of professional experience?"
python -m app.scripts.inspect_final_cv_retrieval `
  --query "Who knows Python and FastAPI?" `
  --candidate-limit 3 `
  --show-context
```

### `inspect_grounded_cv_answer`

Runs final retrieval and answer generation, then prints validated citations and
provider details.

```powershell
python -m app.scripts.inspect_grounded_cv_answer `
  --query "Who has Python and PostgreSQL experience?"
python -m app.scripts.inspect_grounded_cv_answer `
  --query "Who managed 8 engineers?" `
  --candidate-limit 3 `
  --show-context
```

Provider behavior:

- deterministic mode makes no hosted call;
- OpenAI mode may call OpenAI;
- Gemini mode may call Gemini;
- auto mode uses the configured provider selection rules.

## Retrieval validation and paraphrase checks

### `validate_cv_retrieval`

Runs final retrieval against the committed search scenarios without answer
generation.

```powershell
# Every scenario.
python -m app.scripts.validate_cv_retrieval

# One or several scenarios.
python -m app.scripts.validate_cv_retrieval `
  --scenario-id backend_python_fastapi_postgresql
python -m app.scripts.validate_cv_retrieval `
  --scenario-id scenario_001 `
  --scenario-id scenario_002

# Alternative plan or temporary limits.
python -m app.scripts.validate_cv_retrieval `
  --plan app/dataset/candidate_dataset_plan.json `
  --semantic-result-limit 50 `
  --candidate-limit 10
```

This command writes nothing and calls no hosted answer provider.

### `evaluate_cv_query_robustness`

Tests different recruiter phrasings through the final retrieval pipeline without
OpenAI or Gemini.

```powershell
# Complete matrix.
python -m app.scripts.evaluate_cv_query_robustness

# One or several families.
python -m app.scripts.evaluate_cv_query_robustness `
  --family-id numeric_experience `
  --family-id education_phrase `
  --verbose

# One or several exact scenarios.
python -m app.scripts.evaluate_cv_query_robustness `
  --scenario-id scenario_001 `
  --strict

# Print only failures and save the full report.
python -m app.scripts.evaluate_cv_query_robustness `
  --failed-only `
  --json-output data/reports/query-robustness.json
```

Available modifiers:

- `--matrix PATH`: use another matrix file;
- repeat `--family-id` or `--scenario-id` to add selections;
- combine family and scenario filters to narrow the selected scenarios;
- `--semantic-result-limit` and `--candidate-limit`: temporary retrieval limits;
- `--diagnostic-candidate-limit`: number of pre-threshold candidate rows kept;
- `--verbose`: parser and candidate-coverage details;
- `--failed-only`: reduce terminal output, while JSON remains complete;
- `--strict`: return exit status 1 when any expectation fails;
- `--json-output PATH`: write the complete diagnostic report.
