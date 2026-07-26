# Backend tests

## Summary explanation

The backend tests protect the complete application flow: candidate generation,
portrait planning, PDF rendering, ingestion, retrieval, grounded answers, API
contracts, setup scripts, and command-line help. Most tests use deterministic
fixtures or small fakes so they do not require hosted provider calls.

## Test groups

| Prefix or file group | Area covered |
|---|---|
| `test_candidate_*` | Candidate schemas, plans, generation, experience, persistence, uniqueness, and dataset validation. |
| `test_portrait_*`, `test_generate_candidate_portraits_cli.py` | Portrait planning, provider boundaries, image normalisation, validation, and CLI behavior. |
| `test_cv_rendering_*`, `test_cv_pdf_validation.py` | Formatting, render planning, PDF output, and searchable facts. |
| `test_cv_ingestion_*`, `test_cv_chunking.py`, `test_cv_embeddings.py`, `test_cv_chroma_store.py` | PDF selection, extraction, chunks, vectors, Chroma persistence, and idempotency. |
| `test_cv_*retrieval*`, `test_cv_query_*`, `test_cv_evidence_analysis.py` | Raw, assisted, candidate-aware, final, and robustness retrieval behavior. |
| `test_cv_grounded_answer_*`, provider tests | Prompting, provider selection, deterministic mode, answer validation, and citations. |
| `test_api_*`, `test_candidate_catalog_service.py` | Public FastAPI contracts and trusted candidate PDFs. |
| `test_*_cli.py`, `test_script_help_reference.py` | Script arguments, output, side effects, and complete `--help` coverage. |
| `test_local_setup_script.py` | Safe PowerShell and Bash setup behavior. |

## Running tests

From the repository root with the services running:

```powershell
docker compose exec backend pytest
```

Run one section while reading its source:

```powershell
docker compose exec backend pytest tests/test_cv_chunking.py -q
docker compose exec backend pytest tests/test_cv_candidate_ranking.py -q
docker compose exec backend pytest tests/test_api_chat.py -q
```

Use `-k` for one behavior:

```powershell
docker compose exec backend pytest -k "numeric and experience" -q
```

Tests should remain provider-free unless the purpose is to test a provider
adapter with a mocked SDK response.
