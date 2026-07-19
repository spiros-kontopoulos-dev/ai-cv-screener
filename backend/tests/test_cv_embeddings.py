"""Tests for explicit local CV embedding generation."""

from pathlib import Path

import numpy as np
import pytest

from app.cv_ingestion import (
    CvChunk,
    CvEmbeddingConfig,
    CvEmbeddingError,
    CvSourceMetadata,
    SentenceTransformerEmbeddingProvider,
    get_embedding_provider,
)


class FakeSentenceTransformer:
    """Deterministic in-memory replacement for SentenceTransformer."""

    def __init__(self, *, dimension: int = 4, invalid_shape: bool = False) -> None:
        self.dimension = dimension
        self.invalid_shape = invalid_shape
        self.encode_calls = 0

    def get_embedding_dimension(self) -> int:
        return self.dimension

    def encode(self, sentences, **kwargs):
        self.encode_calls += 1
        width = self.dimension - 1 if self.invalid_shape else self.dimension
        matrix = np.asarray(
            [
                [float(index + offset + 1) for offset in range(width)]
                for index, _ in enumerate(sentences)
            ],
            dtype=np.float32,
        )
        if kwargs["normalize_embeddings"]:
            matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix


class LegacyFakeSentenceTransformer(FakeSentenceTransformer):
    """Represent a pre-rename model without the current dimension method."""

    get_embedding_dimension = None

    def get_sentence_embedding_dimension(self) -> int:
        return self.dimension


def test_provider_loads_model_once_and_returns_metadata_rich_vectors() -> None:
    """One provider reuses one model and preserves each source chunk."""

    fake_model = FakeSentenceTransformer()
    load_calls = []

    def loader(model_name: str, device: str, cache_directory: Path):
        load_calls.append((model_name, device, cache_directory))
        return fake_model

    provider = SentenceTransformerEmbeddingProvider(
        CvEmbeddingConfig(
            model_name="example-model",
            expected_dimension=4,
            batch_size=2,
            cache_directory=Path("cache"),
        ),
        model_loader=loader,
    )
    chunks = (_make_chunk("chunk_1", "Python APIs"), _make_chunk("chunk_2", "SQL"))

    first = provider.embed_chunks(chunks)
    second = provider.embed_chunks(chunks[:1])

    assert len(load_calls) == 1
    assert fake_model.encode_calls == 2
    assert first[0].chunk is chunks[0]
    assert first[0].embedding_model == "example-model"
    assert first[0].embedding_dimension == 4
    assert first[0].normalized is True
    assert np.isclose(np.linalg.norm(first[0].embedding), 1.0)
    assert second[0].chunk is chunks[0]


def test_provider_rejects_model_dimension_mismatch_before_encoding() -> None:
    """A model with an unexpected output contract fails before persistence."""

    provider = SentenceTransformerEmbeddingProvider(
        CvEmbeddingConfig(model_name="wrong", expected_dimension=4),
        model_loader=lambda *_: FakeSentenceTransformer(dimension=5),
    )

    with pytest.raises(CvEmbeddingError, match="dimension mismatch"):
        provider.embed_chunks((_make_chunk("chunk_1", "Python"),))


def test_provider_rejects_invalid_embedding_matrix_shape() -> None:
    """The provider validates row count and vector width from the model."""

    provider = SentenceTransformerEmbeddingProvider(
        CvEmbeddingConfig(model_name="wrong-shape", expected_dimension=4),
        model_loader=lambda *_: FakeSentenceTransformer(
            dimension=4,
            invalid_shape=True,
        ),
    )

    with pytest.raises(CvEmbeddingError, match="shape mismatch"):
        provider.embed_chunks((_make_chunk("chunk_1", "Python"),))


def test_provider_embeds_query_text_with_same_contract() -> None:
    """Future retrieval queries can reuse the identical model configuration."""

    provider = SentenceTransformerEmbeddingProvider(
        CvEmbeddingConfig(model_name="example", expected_dimension=4),
        model_loader=lambda *_: FakeSentenceTransformer(),
    )

    vectors = provider.embed_texts(("Who knows Python?", "Backend engineers"))

    assert len(vectors) == 2
    assert all(len(vector) == 4 for vector in vectors)


def test_cached_provider_factory_reuses_identical_configuration() -> None:
    """The process-wide provider cache avoids repeated model initialization."""

    get_embedding_provider.cache_clear()
    first = get_embedding_provider(
        "example",
        4,
        8,
        True,
        "cpu",
        Path("storage/models"),
    )
    second = get_embedding_provider(
        "example",
        4,
        8,
        True,
        "cpu",
        Path("storage/models"),
    )

    assert first is second


def test_provider_supports_legacy_dimension_method_without_breaking() -> None:
    """An older compatible model can still expose the pre-5.4 method."""

    provider = SentenceTransformerEmbeddingProvider(
        CvEmbeddingConfig(model_name="legacy", expected_dimension=4),
        model_loader=lambda *_: LegacyFakeSentenceTransformer(),
    )

    embedded = provider.embed_chunks((_make_chunk("chunk_1", "Python"),))

    assert embedded[0].embedding_dimension == 4


def test_embedding_config_rejects_invalid_values() -> None:
    """Invalid model and batching settings fail before provider work."""

    with pytest.raises(CvEmbeddingError, match="cannot be empty"):
        CvEmbeddingConfig(model_name=" ")
    with pytest.raises(CvEmbeddingError, match="positive"):
        CvEmbeddingConfig(batch_size=0)


def _make_chunk(chunk_id: str, text: str) -> CvChunk:
    source = CvSourceMetadata(
        document_id="document_abc",
        document_hash="a" * 64,
        candidate_id="candidate_001",
        candidate_name="Jane Example",
        professional_title="Backend Engineer",
        source_filename="jane.pdf",
        source_path=Path("/tmp/jane.pdf"),
    )
    return CvChunk(
        chunk_id=chunk_id,
        source=source,
        section_name="experience",
        page_numbers=(1,),
        chunk_index=int(chunk_id.rsplit("_", 1)[-1]) - 1,
        chunking_version="cv-sections-v1",
        text=text,
    )
