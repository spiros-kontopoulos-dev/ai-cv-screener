# API layer

## Summary explanation

This folder exposes the application through FastAPI. It keeps HTTP concerns
separate from candidate generation, indexing, retrieval, and answer generation.
A route validates the request, calls an application service, and converts the
result into the public JSON contract.

```text
HTTP request -> route -> dependency/service -> presenter -> HTTP response
```

## Files

| File | Purpose |
|---|---|
| [`router.py`](router.py) | Combines the route modules under the `/api` prefix. |
| [`dependencies.py`](dependencies.py) | Builds shared settings, catalogue, retrieval, and answer-generation services for route functions. |
| [`schemas.py`](schemas.py) | Defines the public health, candidate, chat, source, and error JSON models. |
| [`presenters.py`](presenters.py) | Converts internal grounded-answer results into the stable chat response returned to React. |
| [`errors.py`](errors.py) | Defines safe public exceptions and installs consistent JSON exception handlers. |
| [`routes/`](routes/README.md) | Contains the health, candidate, CV-file, and chat endpoints. |

## Main rules

- Routes do not read ChromaDB, call providers, or open files directly unless the
  operation belongs to that route's trusted service boundary.
- Provider keys never appear in API responses.
- Candidate PDF paths come from indexed metadata rather than arbitrary user
  input.
- Internal exceptions are translated into safe public error messages.
- The public contract is represented by Pydantic models in `schemas.py` and is
  visible in FastAPI's generated OpenAPI documentation.

## How the chat endpoint works

```text
ChatRequest
-> GroundedCvAnswerGenerator
-> final retrieval result
-> provider or deterministic wording
-> citation validation
-> present_chat_response()
-> ChatResponse
```

## Related tests

- `tests/test_api_health.py`
- `tests/test_api_candidates.py`
- `tests/test_api_chat.py`
- `tests/test_api_cors.py`
- `tests/test_api_openapi.py`

Run the API tests:

```powershell
docker compose exec backend pytest `
  tests/test_api_health.py `
  tests/test_api_candidates.py `
  tests/test_api_chat.py `
  tests/test_api_cors.py `
  tests/test_api_openapi.py
```
