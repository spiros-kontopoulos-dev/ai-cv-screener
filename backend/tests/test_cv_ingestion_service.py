"""Tests for complete idempotent CV ingestion orchestration."""

from pathlib import Path

import numpy as np
import pymupdf

from app.cv_ingestion import (
    CvChromaRepository,
    CvChunkingConfig,
    CvEmbeddingConfig,
    CvIngestionService,
    CvMetadataOverrides,
    CvVectorStoreConfig,
    SentenceTransformerEmbeddingProvider,
)


class FakeModel:
    """Deterministic local embedding model with observable encode calls."""

    def __init__(self) -> None:
        self.encode_calls = 0

    def get_embedding_dimension(self) -> int:
        return 4

    def encode(self, sentences, **kwargs):
        self.encode_calls += 1
        matrix = np.asarray(
            [
                [
                    float(len(text) + 1),
                    float(index + 1),
                    2.0,
                    3.0,
                ]
                for index, text in enumerate(sentences)
            ],
            dtype=np.float32,
        )
        return matrix / np.linalg.norm(matrix, axis=1, keepdims=True)


def test_first_ingestion_indexes_and_second_run_skips_without_reembedding(
    tmp_path: Path,
) -> None:
    """A complete matching document hash bypasses extraction and embeddings."""

    pdf_path = tmp_path / "candidate_001.pdf"
    _write_cv(pdf_path, "Jane Example", "Backend Engineer", "Python FastAPI")
    service, repository, model = _service(tmp_path)

    first = service.ingest((pdf_path,))
    second = service.ingest((pdf_path,))

    assert first.indexed_document_count == 1
    assert first.records_upserted > 0
    assert first.coverage.complete_document_count == 1
    assert second.indexed_document_count == 0
    assert second.skipped_document_count == 1
    assert second.chunks_embedded == 0
    assert second.collection_count == first.collection_count
    assert model.encode_calls == 1
    assert repository.get_document_summaries()[0].complete is True


def test_rebuild_reprocesses_a_complete_document(tmp_path: Path) -> None:
    """Explicit rebuild clears the collection and runs the complete pipeline."""

    pdf_path = tmp_path / "candidate_001.pdf"
    _write_cv(pdf_path, "Jane Example", "Backend Engineer", "Python")
    service, _, model = _service(tmp_path)

    service.ingest((pdf_path,))
    rebuilt = service.ingest((pdf_path,), rebuild=True)

    assert rebuilt.rebuilt is True
    assert rebuilt.indexed_document_count == 1
    assert rebuilt.skipped_document_count == 0
    assert rebuilt.coverage.document_count == 1
    assert model.encode_calls == 2


def test_replace_existing_removes_older_revision_for_same_source_path(
    tmp_path: Path,
) -> None:
    """A changed PDF can explicitly replace its older indexed revision."""

    pdf_path = tmp_path / "candidate_001.pdf"
    _write_cv(pdf_path, "Jane Example", "Backend Engineer", "Python")
    service, repository, _ = _service(tmp_path)
    first = service.ingest((pdf_path,))
    old_hash = first.results[0].document_hash

    _write_cv(
        pdf_path,
        "Jane Example",
        "Senior Backend Engineer",
        "Python FastAPI PostgreSQL",
    )
    second = service.ingest((pdf_path,), replace_existing=True)

    assert second.indexed_document_count == 1
    assert second.records_deleted > 0
    assert repository.get_document_summary(old_hash) is None
    assert second.coverage.document_count == 1


def test_duplicate_selected_content_is_reported_without_duplicate_vectors(
    tmp_path: Path,
) -> None:
    """Two paths containing identical bytes become one technical document."""

    first_path = tmp_path / "a.pdf"
    second_path = tmp_path / "b.pdf"
    _write_cv(first_path, "Jane Example", "Backend Engineer", "Python")
    second_path.write_bytes(first_path.read_bytes())
    service, _, model = _service(tmp_path)

    summary = service.ingest((first_path, second_path))

    assert summary.selected_pdf_count == 2
    assert summary.unique_pdf_count == 1
    assert summary.duplicate_input_count == 1
    assert summary.indexed_document_count == 1
    assert model.encode_calls == 1


def test_corrupt_document_failure_does_not_block_valid_document(tmp_path: Path) -> None:
    """Document-level extraction failures are reported while valid PDFs continue."""

    valid_path = tmp_path / "candidate_001.pdf"
    corrupt_path = tmp_path / "broken.pdf"
    _write_cv(valid_path, "Jane Example", "Backend Engineer", "Python")
    corrupt_path.write_bytes(b"not a real pdf")
    service, _, _ = _service(tmp_path)

    summary = service.ingest((valid_path, corrupt_path))

    assert summary.indexed_document_count == 1
    assert summary.failed_document_count == 1
    assert summary.coverage.document_count == 1
    assert summary.failures[0].stage == "processing"


def test_renamed_identical_pdf_refreshes_metadata_without_reembedding(
    tmp_path: Path,
) -> None:
    """Content identity survives a rename while source display metadata changes."""

    original = tmp_path / "candidate_001.pdf"
    renamed = tmp_path / "jane-example-backend-engineer-cv.pdf"
    _write_cv(original, "Jane Example", "Backend Engineer", "Python")
    service, repository, model = _service(tmp_path)
    first = service.ingest((original,))
    original.rename(renamed)

    second = service.ingest((renamed,))
    stored = repository.get_document_summary(first.results[0].document_hash)

    assert second.metadata_refreshed_count == 1
    assert second.indexed_document_count == 0
    assert model.encode_calls == 1
    assert stored is not None
    assert stored.source_filename == renamed.name
    assert stored.source_path == renamed.resolve().as_posix()


def test_incomplete_document_is_rebuilt_on_the_next_scan(tmp_path: Path) -> None:
    """A partial prior write is deleted and restored instead of being skipped."""

    pdf_path = tmp_path / "candidate_001.pdf"
    _write_cv(pdf_path, "Jane Example", "Backend Engineer", "Python FastAPI")
    service, repository, model = _service(tmp_path)
    first = service.ingest((pdf_path,))
    document_hash = first.results[0].document_hash
    stored_ids = repository.collection.get(
        where={"document_hash": document_hash},
        include=["metadatas"],
    )["ids"]
    repository.collection.delete(ids=[stored_ids[0]])

    repaired = service.ingest((pdf_path,))

    assert repaired.indexed_document_count == 1
    assert repaired.records_deleted > 0
    assert repaired.coverage.incomplete_document_count == 0
    assert repository.get_document_summary(document_hash).complete is True
    assert model.encode_calls == 2


def test_metadata_overrides_support_arbitrary_uploaded_style_pdf(
    tmp_path: Path,
) -> None:
    """Future upload metadata can override best-effort header detection."""

    pdf_path = tmp_path / "resume.pdf"
    _write_cv(pdf_path, "Unknown Header", "Software Professional", "Python")
    service, repository, _ = _service(tmp_path)

    summary = service.ingest(
        (pdf_path,),
        metadata_overrides=CvMetadataOverrides(
            candidate_id="candidate_external_001",
            candidate_name="Spiros Example",
            professional_title="Senior Python Engineer",
        ),
    )
    stored = repository.get_document_summaries()[0]

    assert summary.indexed_document_count == 1
    assert stored.candidate_id == "candidate_external_001"
    assert stored.candidate_name == "Spiros Example"


def _service(
    tmp_path: Path,
) -> tuple[CvIngestionService, CvChromaRepository, FakeModel]:
    model = FakeModel()
    provider = SentenceTransformerEmbeddingProvider(
        CvEmbeddingConfig(
            model_name="test-model",
            expected_dimension=4,
            batch_size=16,
            cache_directory=tmp_path / "models",
        ),
        model_loader=lambda *_: model,
    )
    repository = CvChromaRepository(
        CvVectorStoreConfig(
            persist_directory=tmp_path / "chroma",
            collection_name="cv_chunks",
            index_version="cv-index-v1",
            embedding_model="test-model",
            embedding_dimension=4,
            chunking_version="cv-sections-v1",
            distance_metric="cosine",
        )
    )
    return (
        CvIngestionService(
            chunking_config=CvChunkingConfig(
                version="cv-sections-v1",
                max_characters=500,
                min_characters=20,
                overlap_characters=50,
            ),
            embedding_provider=provider,
            repository=repository,
        ),
        repository,
        model,
    )


def _write_cv(path: Path, name: str, title: str, evidence: str) -> None:
    if path.exists():
        path.unlink()
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        f"{name}\n{title}\nPROFESSIONAL PROFILE\n{evidence}\n"
        f"WORK EXPERIENCE\nBuilt systems with {evidence}.\n"
        f"SKILLS\n{evidence}",
    )
    document.save(path)
    document.close()


def test_complete_committed_collection_is_idempotent_in_real_chroma(
    tmp_path: Path,
) -> None:
    """All 30 PDFs become 184 complete vectors and the second scan skips all."""

    pdf_directory = _resolve_committed_pdf_directory()
    paths = tuple(sorted(pdf_directory.glob("*.pdf")))
    model = FakeModel()
    provider = SentenceTransformerEmbeddingProvider(
        CvEmbeddingConfig(
            model_name="test-model",
            expected_dimension=4,
            batch_size=32,
            cache_directory=tmp_path / "models",
        ),
        model_loader=lambda *_: model,
    )
    repository = CvChromaRepository(
        CvVectorStoreConfig(
            persist_directory=tmp_path / "chroma-complete",
            collection_name="cv_chunks",
            index_version="cv-index-v1",
            embedding_model="test-model",
            embedding_dimension=4,
            chunking_version="cv-sections-v1",
            distance_metric="cosine",
        )
    )
    service = CvIngestionService(
        chunking_config=CvChunkingConfig(),
        embedding_provider=provider,
        repository=repository,
    )

    first = service.ingest(paths)
    second = service.ingest(paths)
    reopened_repository = CvChromaRepository(repository.config)
    reopened_coverage = reopened_repository.get_index_coverage()

    assert first.selected_pdf_count == 30
    assert first.indexed_document_count == 30
    assert first.pages_extracted == 59
    assert first.chunks_generated == 184
    assert first.records_upserted == 184
    assert first.coverage.complete_document_count == 30
    assert first.coverage.incomplete_document_count == 0
    assert second.skipped_document_count == 30
    assert second.chunks_embedded == 0
    assert second.collection_count == 184
    assert reopened_coverage.record_count == 184
    assert reopened_coverage.complete_document_count == 30
    assert model.encode_calls == 1


def _resolve_committed_pdf_directory() -> Path:
    """Resolve shared PDF fixtures in Docker and direct host execution."""

    candidates = (
        Path("/app/data/cv_pdfs"),
        Path(__file__).resolve().parents[2] / "data" / "cv_pdfs",
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise AssertionError("Committed CV PDF directory could not be resolved.")
