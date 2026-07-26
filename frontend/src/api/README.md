# Frontend API client and contracts

## Summary explanation

This folder is the browser's only HTTP boundary. It defines the TypeScript shape
of public FastAPI responses and centralises URL building, timeouts,
cancellation, JSON parsing and safe error messages.

Components do not call `fetch()` directly.

## Position in the frontend flow

```text
App action
-> client function
-> requestJson()
-> FastAPI endpoint
-> typed response or ApiClientError
-> App state update
-> component render
```

Before this section, the frontend has an intent such as “load candidates” or
“ask this question”. After it returns, `App` has a typed result or one stable
error object.

## Files

| File | Runtime role |
|---|---|
| [`types.ts`](types.ts) | Mirrors the public FastAPI health, candidate, chat, source and error contracts. |
| [`client.ts`](client.ts) | Implements the reusable HTTP client and endpoint-specific functions. |
| [`client.test.ts`](client.test.ts) | Tests URLs, success parsing, API errors, timeouts, network failures and cancellation. |

## Exact request order

```text
getHealth() / getCandidates() / askQuestion()
-> requestJson(path, init, externalSignal)
-> createRequestSignal()
   -> create internal AbortController
   -> forward external cancellation
   -> start timeout
-> fetch(buildApiUrl(path), ...)
-> if response not OK: parseErrorResponse()
-> else response.json() as the requested type
-> cleanup timeout and event listener
```

## Important functions and classes

### `API_BASE_URL`

Built once from `VITE_API_BASE_URL` or the local default. `normalizeBaseUrl()`
removes trailing slashes so path joining remains predictable.

### `buildApiUrl(path)`

Accepts either a relative API path or an already absolute URL. Relative paths
are joined to the configured API base URL.

### `createRequestSignal(externalSignal, timeoutMs)`

Combines two cancellation sources:

- the caller can cancel because the component unmounted or a newer request started;
- the client can cancel when the timeout expires.

It also returns `cleanup()` so timers and listeners are always removed.

### `requestJson<T>(...)`

The shared request pipeline. It:

- sends `Accept: application/json`;
- checks `response.ok`;
- parses public JSON errors;
- distinguishes timeout, caller cancellation and network failure;
- throws only `ApiClientError` to application code.

### `ApiClientError`

Carries:

- safe message;
- stable error code;
- HTTP status when present;
- structured validation details.

`App.errorMessage()` can therefore display backend messages without understanding
all HTTP implementation details.

### Endpoint functions

```text
getHealth(signal?)
-> GET /api/health

getCandidates(signal?)
-> GET /api/candidates

askQuestion(request, signal?)
-> POST /api/chat with JSON body
```

### `getCandidatePhotoUrl(candidateId)`

Builds the static frontend image URL for a known candidate ID. Candidate photos
are presentation assets; source evidence still comes from the PDF API.

## Contract direction

`types.ts` should change only when the public FastAPI schema changes. Internal
backend dataclasses do not need matching TypeScript definitions unless their
fields are exposed by the API presenter.

Important response flow:

```text
backend GroundedAnswerGenerationResult
-> API present_chat_response()
-> ChatResponse JSON
-> frontend ChatResponse type
-> App and components
```

## Error behavior

| Situation | `ApiClientError.code` or behavior |
|---|---|
| Public API error JSON | Uses backend code/message/details. |
| Non-JSON server failure | `http_error` with safe generic wording. |
| Request timeout | `request_timeout`. |
| Caller cancellation | `request_cancelled`. |
| Cannot reach backend | `network_error`. |

## Important boundary

Only public configuration belongs in Vite variables. Provider keys and backend
filesystem paths must never be placed in `VITE_*` values because those values
are visible to the browser.
