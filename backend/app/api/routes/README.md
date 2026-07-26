# API routes

## Summary explanation

These modules contain the public HTTP endpoints. They are intentionally small:
request validation belongs to API schemas, business logic belongs to services,
and response conversion belongs to presenters.

## Route modules

| File | Endpoints and responsibility |
|---|---|
| [`health.py`](health.py) | `GET /api/health` reports provider configuration and CV-index readiness. |
| [`candidates.py`](candidates.py) | `GET /api/candidates` lists indexed candidates. `GET /api/candidates/{candidate_id}/cv` opens a trusted PDF. |
| [`chat.py`](chat.py) | `POST /api/chat` accepts a recruiter question and returns grounded candidates, answer text, scores, and sources. |

## Request path

```text
FastAPI validates request
-> dependency provides service
-> route calls service
-> known failures become PublicApiError variants
-> Pydantic response model is returned
```

## Important boundary

The CV endpoint does not accept a filesystem path from the browser. It accepts a
candidate ID, resolves the trusted PDF through the candidate catalogue, and then
returns that file. This prevents arbitrary local file access.

See the parent [`API guide`](../README.md) for the schemas, dependencies,
presenters, and exception handling used by these routes.
