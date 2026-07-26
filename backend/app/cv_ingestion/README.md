# CV ingestion and vector-index pipeline

## Summary explanation

This section converts the validated PDF CV collection into the persistent search
index. It is the handoff from document creation to runtime retrieval.

The PDF is the source of truth. This pipeline reads the PDF bytes, extracts text,
creates candidate-safe chunks, embeds those chunks with a local Sentence
Transformer and stores the vectors plus traceable metadata in ChromaDB.

## Position in the complete application

### State before this section

- the candidate profile and portrait pipelines have already produced final PDFs;
- the PDFs have been validated as readable and fact-complete;
- `storage/chroma` may be empty, complete, partial or built with incompatible settings.

### State after this section

- every indexed PDF has a SHA-256 document identity;
- every document has extracted page text and candidate metadata;
- every document has stable section-aware chunks;
- every chunk has a normalised 384-dimensional vector by default;
- Chroma contains complete, source-traceable records;
- retrieval can embed a recruiter question with the same model and query the collection.

```text
Validated PDF CVs
-> selected paths
-> SHA-256 fingerprints and duplicate checks
-> PyMuPDF text extraction
-> candidate/header detection
-> section fragments
-> packed chunk drafts
-> validated CvChunk objects
-> local embeddings
-> Chroma upsert
-> index coverage summary
```

## Actual entry point and orchestrator

The normal command starts in:

```text
app.scripts.ingest_cv_documents.run_cli()
```

That script performs input selection and service construction. The central
orchestrator is:

```text
cv_ingestion.ingestion.CvIngestionService.ingest()
```

This distinction matters: `ingestion.py` appears later alphabetically, but it is
the file that calls the extraction, chunking, embedding and storage stages.

## Exact runtime order

### Command and service construction

```text
1. run_cli() parses --file, --directory, --all and update options.
2. get_settings() supplies default paths and compatibility settings.
3. select_cv_pdf_paths() returns a deterministic list of validated PDF paths.
4. _build_service() creates:
   a. cached SentenceTransformerEmbeddingProvider;
   b. CvChromaRepository with collection compatibility metadata;
   c. CvChunkingConfig;
   d. CvIngestionService.
5. run_cli() calls CvIngestionService.ingest(paths, ...).
```

### Inside `CvIngestionService.ingest()`

```text
1. Validate that at least one path exists and metadata overrides are legal.
2. Sort paths deterministically.
3. If --rebuild is active, reset the Chroma collection.
4. calculate_pdf_sha256() for every selected file.
5. Remove duplicate selected contents by document hash.
6. Ask CvChromaRepository for existing summaries by hash.
7. For complete unchanged documents:
   a. skip them; or
   b. refresh only source-path metadata when the file moved.
8. For each pending document:
   a. load_cv_document() extracts pages and candidate metadata;
   b. verify the bytes did not change after fingerprinting;
   c. chunk_cv_document() creates the final CvChunk collection.
9. Flatten all pending chunks and embed them in one provider call.
10. Regroup EmbeddedCvChunk objects by document hash.
11. For each pending document:
    a. delete incomplete or replaced old records when required;
    b. upsert the document's chunks and vectors;
    c. record pages, chunks and candidate status.
12. Read final collection count and index coverage.
13. Return CvIngestionSummary with results and failures.
```

The expensive stages are deliberately delayed. Unchanged complete PDFs are
identified by hash before text extraction or embedding.

## File map by runtime phase

| Runtime phase | File | Responsibility |
|---:|---|---|
| 1 | [`selection.py`](selection.py) | Selects and validates one PDF, several PDFs, a directory, or the configured collection. |
| 2 | [`ingestion.py`](ingestion.py) | Orchestrates the complete operation and decides skip, refresh, replace, index or fail status. |
| 3 | [`extraction.py`](extraction.py) | Fingerprints PDF bytes, extracts sorted page text with PyMuPDF and detects candidate metadata. |
| 4 | [`sectioning.py`](sectioning.py) | Splits page text into ordered CV section fragments. |
| 5 | [`chunk_packing.py`](chunk_packing.py) | Converts fragments into size-limited drafts with controlled overlap. |
| 6 | [`chunking.py`](chunking.py) | Builds and validates final `CvChunk` objects with stable IDs. |
| 7 | [`embeddings.py`](embeddings.py) | Loads/caches the local Sentence Transformer and embeds chunks or questions using the same settings. |
| 8 | [`chroma_store.py`](chroma_store.py) | Creates, checks, reads, writes, deletes and summarises the persistent Chroma collection. |
| Shared | [`models.py`](models.py) | Defines source metadata, extracted pages/documents, chunks and rename plans passed between stages. |
| Optional side flow | [`naming.py`](naming.py) | Plans and applies human-readable PDF filenames without changing SHA-256 identity. |

`models.py` is used throughout the pipeline; it is not a separate execution
step. `naming.py` belongs to a related maintenance command and is not part of
the main PDF-to-vector path.

## Important functions and classes

### `select_cv_pdf_paths(...)`

Implements all input modes and returns one sorted tuple. It rejects invalid
combinations and uses `validate_cv_pdf_path()` so non-PDF or missing files do
not reach the ingestion service.

### `calculate_pdf_sha256(path)`

Streams the raw file bytes into SHA-256. The hash is the document identity:
renaming the file does not create a second logical document.

### `load_cv_document(path, metadata overrides...)`

The main extraction function:

```text
calculate hash
-> open PDF with PyMuPDF
-> extract sorted text for every page
-> normalise page text
-> detect candidate ID, name and professional title
-> build ExtractedCvDocument
```

Metadata overrides are allowed only for a single unknown-layout PDF.

### `split_document_into_sections(document)`

Walks the extracted lines, recognises headings and produces `SectionFragment`
objects while preserving page references. Unknown layouts still receive safe
fallback fragments instead of being discarded.

### `fragment_to_units()` and `pack_section_units()`

`chunk_packing.py` separates text splitting from final chunk construction:

- fragments become smaller `TextUnit` objects;
- long units are split at readable boundaries;
- units are packed up to the character limit;
- a controlled tail from the previous draft becomes overlap;
- very small final drafts may be merged safely.

### `chunk_cv_document(document, config)`

Coordinates sectioning and packing, then creates final `CvChunk` objects.
`build_chunk_id()` uses stable document and chunk information so repeated runs
with the same rules produce the same IDs.

`_validate_chunks()` checks ordering, uniqueness, sizes, source identity and
candidate isolation before the chunks can be embedded.

### `get_embedding_provider(...)`

Returns a cached `SentenceTransformerEmbeddingProvider`. The same provider
configuration is used by ingestion and raw retrieval, which guarantees that CV
chunks and recruiter questions live in the same vector space.

### `SentenceTransformerEmbeddingProvider.embed_chunks(chunks)`

Embeds chunk text in configured batches and returns `EmbeddedCvChunk` objects.
It checks vector count, dimension and finite values before storage.

### `CvChromaRepository`

The persistent storage boundary. Important operations include:

- `reset_collection()`;
- `get_collection_info()`;
- `get_document_summaries()`;
- `upsert_embeddings()`;
- `delete_document_records()`;
- `query_nearest()`;
- `get_all_chunks()`;
- `get_index_coverage()`.

When it opens a collection, it checks metadata such as embedding model,
dimension, chunking version, index version and distance metric.

### `CvIngestionService.ingest(...)`

The central coordinator described above. It returns a `CvIngestionSummary`
rather than printing. The CLI prints that result; a future upload endpoint could
reuse the same service without copying pipeline logic.

## Data objects passed through the pipeline

```text
Path
-> ExtractedCvPage
-> ExtractedCvDocument
-> SectionFragment
-> TextUnit
-> ChunkDraft
-> CvChunk
-> EmbeddedCvChunk
-> Chroma record
```

The final stored metadata includes enough information to trace evidence back to
its source:

- candidate ID, candidate name and professional title;
- document hash, source filename and source path;
- page start/end and section name;
- chunk index, chunk ID and expected chunk count;
- embedding, chunking and index compatibility values.

## Idempotency and replacement behavior

### Same complete PDF again

```text
same SHA-256 + complete stored document
-> skip extraction
-> skip embedding
-> no duplicate records
```

### Same bytes at a new path

When the old stored path no longer exists, only filename/path metadata can be
refreshed. Vectors do not need to be recalculated.

### Partial stored document

Old partial records are deleted and the complete document is rebuilt.

### `--replace-existing`

The service deletes records that belong to the replaced source path or candidate
before writing the new document.

### `--rebuild`

Resets the collection before any selected PDF is processed. Use it when
embedding, chunking or index compatibility settings change.

## Failure handling

Failures are recorded by stage:

- `fingerprint` — file could not be read or hashed;
- `metadata` — stored path metadata could not be refreshed;
- `processing` — extraction, candidate detection or chunking failed;
- `embedding` — vector creation failed;
- storage failures — converted to a safe `CvIngestionError`.

A failed document is never reported as complete. The final CLI also fails when
index coverage contains incomplete documents.

## Connection to the next section

```text
persistent Chroma collection
-> cv_retrieval.raw_retrieval embeds a recruiter question
-> CvChromaRepository.query_nearest()
-> source-traceable RawCvRetrievalHit objects
```

The candidate catalogue service also reads this same collection to build the
browser sidebar.

## Main commands

```powershell
docker compose -p ai-cv-screener-openai exec backend `
  python -m app.scripts.ingest_cv_documents --help

docker compose -p ai-cv-screener-openai exec backend `
  python -m app.scripts.inspect_cv_documents --help

docker compose -p ai-cv-screener-openai exec backend `
  python -m app.scripts.inspect_cv_chunks --help

docker compose -p ai-cv-screener-openai exec backend `
  python -m app.scripts.inspect_cv_embeddings --help

docker compose -p ai-cv-screener-openai exec backend `
  python -m app.scripts.inspect_cv_vector_store --help
```

## Related tests

- `test_cv_ingestion_loading.py`
- `test_cv_chunking.py`
- `test_cv_embeddings.py`
- `test_cv_chroma_store.py`
- `test_cv_ingestion_service.py`
- `test_cv_ingestion_naming.py`
- `test_ingest_cv_documents_cli.py`
- the `inspect_cv_*_cli.py` test files
