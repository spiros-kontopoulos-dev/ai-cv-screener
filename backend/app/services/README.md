# Shared application services

## Summary explanation

This folder contains reusable application services that do not belong to HTTP
handling. At present it contains the read-only candidate catalogue used by the
health and candidate routes.

The catalogue is built from indexed PDF metadata, not from generated profile
JSON. The browser therefore sees the same candidates that are actually
searchable.

## Position in the architecture

### State before this section

- Chroma contains PDF-derived chunks and metadata;
- API routes need a stable candidate list, index coverage and trusted PDF lookup;
- routes should not know Chroma details or filesystem safety rules.

### State after this section

- one `IndexedCandidate` exists per indexed candidate ID;
- health can read index coverage;
- the sidebar can list candidate identity;
- the PDF route can resolve only a trusted file within configured roots.

```text
Chroma stored chunks
-> CandidateCatalogService
-> grouped IndexedCandidate objects
-> list / lookup / coverage / trusted PDF path
-> API routes
```

## Files

| File | Runtime role |
|---|---|
| [`candidate_catalog.py`](candidate_catalog.py) | Reads indexed chunks, constructs candidate catalogue rows and resolves trusted PDFs. |
| [`__init__.py`](__init__.py) | Re-exports the service, builder, models and stable error types. |

## Service construction

```text
api.dependencies.get_candidate_catalog_service()
-> build_candidate_catalog_service(get_settings())
-> CvChromaRepository configured with the same collection metadata
-> CandidateCatalogService(settings, repository)
-> cached service reused by routes
```

## Exact candidate-list flow

```text
CandidateCatalogService.list_candidates()
-> repository.get_all_chunks()
-> validate candidate_id in every chunk
-> group chunks by candidate_id
-> _build_candidate() for every group
-> require consistent name, title, filename and source metadata
-> determine PDF and portrait availability
-> sort by candidate_id
-> tuple[IndexedCandidate, ...]
```

The service does not assume that the first arbitrary chunk contains perfect
metadata. It builds a stable candidate row from the grouped indexed evidence.

## Important functions and classes

### `IndexedCandidate`

The read-only catalogue row returned to the API. It contains candidate ID, name,
professional title, source filename/path and availability flags.

### `CandidateCatalogService.list_candidates()`

Builds the complete catalogue from Chroma records. Invalid or conflicting
metadata becomes `CandidateCatalogError` rather than a partially trusted list.

### `get_index_coverage()`

Delegates to `CvChromaRepository.get_index_coverage()` and translates storage
errors into the service's stable error type. The health route uses this method.

### `get_candidate(candidate_id)`

Validates the candidate-ID format, calls `list_candidates()` and returns one
matching row or `CandidateNotFoundError`.

### `resolve_candidate_pdf(candidate_id)`

The trusted file-resolution boundary:

```text
candidate ID
-> indexed candidate row
-> validate filename is a plain .pdf name
-> create candidate paths from indexed path and configured PDF roots
-> resolve each path
-> require path to remain inside an allowed root
-> require existing .pdf file
-> return trusted Path
```

The browser never supplies a filesystem path.

## Important safety rule

The allowed roots are:

- `cv_ingestion_default_directory`;
- `cv_pdfs_output_directory`.

A stored path outside those roots is ignored. Path traversal, arbitrary
extensions and missing files produce `CandidatePdfUnavailableError`.

## Connection to API routes

```text
GET /api/health
-> get_index_coverage()

GET /api/candidates
-> list_candidates()

GET /api/candidates/{candidate_id}/cv
-> get_candidate()
-> resolve_candidate_pdf()
-> FileResponse
```

## Related tests

- `test_candidate_catalog_service.py`
- `test_api_candidates.py`
- `test_api_health.py`
