# CV ingestion and vector index

## Summary explanation

This section converts the rendered PDF CV collection into the persistent search
index. It keeps the PDF as the source of truth, creates candidate-safe chunks,
embeds each chunk locally, and stores the vectors plus traceable metadata in
ChromaDB.

```text
PDF files
-> SHA-256 identity and page extraction
-> section detection
-> bounded chunks with stable IDs
-> local Sentence Transformer embeddings
-> persistent ChromaDB collection
```

## Files

| File | Purpose |
|---|---|
| [`selection.py`](selection.py) | Selects one PDF, many PDFs, a directory, or the configured collection. |
| [`extraction.py`](extraction.py) | Calculates document hashes, extracts page text with PyMuPDF, and detects candidate metadata. |
| [`sectioning.py`](sectioning.py) | Splits page text into familiar CV sections such as summary, skills, experience, and education. |
| [`chunk_packing.py`](chunk_packing.py) | Packs section text into size-limited units with controlled overlap. |
| [`chunking.py`](chunking.py) | Builds validated `CvChunk` objects and stable chunk IDs. |
| [`embeddings.py`](embeddings.py) | Loads the local Sentence Transformer and embeds chunks and questions with matching settings. |
| [`chroma_store.py`](chroma_store.py) | Creates, checks, writes, reads, and summarises the persistent Chroma collection. |
| [`ingestion.py`](ingestion.py) | Coordinates the complete PDF-to-index pipeline and idempotent update behavior. |
| [`models.py`](models.py) | Data objects passed between extraction, chunking, naming, and storage stages. |
| [`naming.py`](naming.py) | Plans optional readable filenames without changing document identity. |

## Identity and idempotency

The SHA-256 hash of the PDF bytes is the document identity. Renaming a file does
not create a new document. Re-ingesting unchanged PDFs does not duplicate their
chunks. A rebuild is required when compatibility settings such as the embedding
model, vector dimension, chunking version, or index version change.

## Source metadata

Each stored chunk keeps enough information to trace an answer back to the PDF:

- candidate ID and candidate header;
- document hash and source path;
- page numbers and section name;
- chunk ID and chunk index;
- embedding and chunking compatibility metadata.

## Main commands

```powershell
docker compose exec backend python -m app.scripts.ingest_cv_documents --help
docker compose exec backend python -m app.scripts.inspect_cv_documents --help
docker compose exec backend python -m app.scripts.inspect_cv_chunks --help
docker compose exec backend python -m app.scripts.inspect_cv_embeddings --help
docker compose exec backend python -m app.scripts.inspect_cv_vector_store --help
```

See [`../scripts/README.md`](../scripts/README.md) for every valid combination.
