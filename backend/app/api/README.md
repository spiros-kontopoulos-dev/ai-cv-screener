# API route execution flows

## Summary explanation

These modules are the public endpoint functions. They are intentionally small.
Each route receives a validated request and an injected service, calls one main
application operation, maps expected failures and returns a public response.

## Position in the architecture

```text
React or browser
-> FastAPI route
-> injected service
-> domain pipeline
-> public schema / FileResponse
-> browser
```

The route files are the HTTP entry points, not the place where retrieval or
storage algorithms live.

## Route registration order

```text
api/router.py
-> APIRouter(prefix="/api")
-> health.router
-> candidates.router
-> chat.router
-> app.main includes api_router
```

## `health.py` runtime order

### Endpoint

```text
GET /api/health
```

### Function flow

```text
health_check(settings, catalog)
-> _provider_status(settings)
   -> resolve_grounded_answer_provider()
   -> report requested mode, active provider, model and readiness
-> catalog.get_index_coverage()
   -> record/document/candidate completeness
-> status = ok only when provider ready and index available
-> HealthResponse
```

A missing or unreadable index becomes degraded health rather than an unhandled
500 response. API keys and provider error details are never returned.

Important functions:

- `health_check()` — combines provider and index readiness;
- `_provider_status()` — uses the same provider resolver as real chat requests.

## `candidates.py` runtime order

### Candidate list

```text
GET /api/candidates
-> list_candidates(catalog)
-> catalog.list_candidates()
-> convert IndexedCandidate rows to CandidateListItem
-> CandidateListResponse
```

### Candidate PDF

```text
GET /api/candidates/{candidate_id}/cv
-> open_candidate_cv(candidate_id, catalog)
-> catalog.get_candidate(candidate_id)
-> catalog.resolve_candidate_pdf(candidate_id)
-> FileResponse(media_type="application/pdf", inline)
```

Known failures are translated:

- unknown ID -> `candidate_not_found` / 404;
- PDF unavailable -> `candidate_cv_not_found` / 404;
- index unavailable -> `candidate_index_unavailable` / 503.

Important functions:

- `list_candidates()` — builds the sidebar response;
- `open_candidate_cv()` — serves a trusted PDF path resolved by the service.

## `chat.py` runtime order

### Endpoint

```text
POST /api/chat
```

### Function flow

```text
FastAPI validates ChatRequest
-> ask_candidates(request, generator)
-> FinalCvRetrievalQuery(question, candidate_limit)
-> generator.generate(query)
   -> final retrieval
   -> provider/deterministic wording
   -> citation validation
-> present_chat_response(result)
-> ChatResponse
```

An unsupported question is a successful HTTP request. It returns HTTP 200 with
`outcome="unsupported"` because the application completed the search and found
insufficient evidence.

Known failures are separated by where they occurred:

- provider configuration missing -> 503;
- hosted provider called and failed -> 502;
- local retrieval unavailable before provider call -> 503.

Important function:

- `ask_candidates()` — the only public HTTP entry point for the complete
  recruiter-question flow.

## Route-to-service map

| Route function | Main service call | Final response |
|---|---|---|
| `health_check()` | `resolve_grounded_answer_provider()` and `catalog.get_index_coverage()` | `HealthResponse` |
| `list_candidates()` | `catalog.list_candidates()` | `CandidateListResponse` |
| `open_candidate_cv()` | `catalog.resolve_candidate_pdf()` | `FileResponse` |
| `ask_candidates()` | `generator.generate()` | `ChatResponse` through presenter |

## Important boundary

No route accepts a filesystem path, Chroma query, provider prompt or citation
list from the browser. The browser supplies only public inputs such as a
candidate ID or recruiter question.

See [`../README.md`](../README.md) for dependency construction, schemas,
presenters and exception handling.
