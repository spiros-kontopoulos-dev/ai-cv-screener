# Shared application services

## Summary explanation

This folder contains small services that are shared by API routes but do not
belong to HTTP handling itself. At present it contains the read-only candidate
catalogue built from the persisted vector index.

## Files

| File | Purpose |
|---|---|
| [`candidate_catalog.py`](candidate_catalog.py) | Reads indexed document metadata, builds one catalogue entry per candidate, and resolves trusted PDF paths. |

## Candidate catalogue flow

```text
Chroma document metadata
-> group by candidate ID
-> validate candidate name, title, pages, and PDF source
-> sort stable catalogue entries
-> expose read-only list and lookup methods
```

The catalogue does not read `candidate_profiles.json`. This keeps the browser's
candidate list aligned with the documents that are actually indexed and
searchable.

## Safety rule

When the API opens a CV, the service resolves the candidate ID to a trusted
indexed PDF path. The browser cannot provide an arbitrary local path.

## Related tests

- `tests/test_candidate_catalog_service.py`
- `tests/test_api_candidates.py`
