# Frontend API client

## Summary explanation

This folder is the browser boundary to the FastAPI backend. It defines the
public TypeScript contracts and keeps URL construction, JSON parsing, request
errors, and PDF links out of the React components.

## Files

| File | Purpose |
|---|---|
| [`types.ts`](types.ts) | TypeScript models matching the backend health, candidate, chat, source, and error responses. |
| [`client.ts`](client.ts) | Fetch helpers for health, candidate catalogue, grounded chat, and candidate PDF URLs. |
| [`client.test.ts`](client.test.ts) | Tests successful responses, public errors, malformed responses, network failures, and URL creation. |

## Request flow

```text
React component
-> typed client function
-> fetch
-> check HTTP status
-> parse JSON
-> return typed data or ApiClientError
```

## Security boundary

Only public browser configuration belongs here. Provider API keys remain in the
backend `.env` file and must never be placed in `VITE_` variables, because Vite
variables are visible to the browser.
