"""Local Hugging Face embedding generation for PDF-derived CV chunks.

The model is loaded lazily and cached by configuration. Chroma never receives
an embedding function; this module owns every vector so the manual RAG workflow
remains visible, testable, and reusable for both document and query embeddings.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from app.cv_ingestion.models import CvChunk


class CvEmbeddingError(RuntimeError):
    """Raised when local embedding generation cannot produce valid vectors."""


class SentenceTransformerModel(Protocol):
    """Small protocol covering the SentenceTransformer methods we depend on."""

    def encode(
        self,
        sentences: Sequence[str],
        *,
        batch_size: int,
        show_progress_bar: bool,
        convert_to_numpy: bool,
        normalize_embeddings: bool,
    ) -> Any:
        """Encode text into a two-dimensional embedding matrix."""

    def get_embedding_dimension(self) -> int | None:
        """Return the model's output dimension when available."""


ModelLoader = Callable[[str, str, Path], SentenceTransformerModel]


@dataclass(frozen=True, slots=True)
class CvEmbeddingConfig:
    """Deterministic model and batching settings for CV embeddings."""

    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    expected_dimension: int = 384
    batch_size: int = 32
    normalize_embeddings: bool = True
    device: str = "cpu"
    cache_directory: Path = Path("storage/models")

    def __post_init__(self) -> None:
        """Reject invalid embedding settings before loading a large model."""

        if not self.model_name.strip():
            raise CvEmbeddingError("Embedding model name cannot be empty.")
        if self.expected_dimension < 1:
            raise CvEmbeddingError("Expected embedding dimension must be positive.")
        if self.batch_size < 1:
            raise CvEmbeddingError("Embedding batch size must be positive.")
        if not self.device.strip():
            raise CvEmbeddingError("Embedding device cannot be empty.")


@dataclass(frozen=True, slots=True)
class EmbeddedCvChunk:
    """One CV chunk paired with its validated dense vector."""

    chunk: CvChunk
    embedding: tuple[float, ...]
    embedding_model: str
    embedding_dimension: int
    normalized: bool


class SentenceTransformerEmbeddingProvider:
    """Lazily load one Sentence Transformer and embed CV chunk batches."""

    def __init__(
        self,
        config: CvEmbeddingConfig,
        *,
        model_loader: ModelLoader | None = None,
    ) -> None:
        self._config = config
        self._model_loader = model_loader or _load_sentence_transformer_model
        self._model: SentenceTransformerModel | None = None

    @property
    def config(self) -> CvEmbeddingConfig:
        """Return the immutable provider configuration."""

        return self._config

    @property
    def model(self) -> SentenceTransformerModel:
        """Load the model once for this provider and reuse it thereafter."""

        if self._model is None:
            try:
                self._config.cache_directory.mkdir(parents=True, exist_ok=True)
                self._model = self._model_loader(
                    self._config.model_name,
                    self._config.device,
                    self._config.cache_directory,
                )
            except CvEmbeddingError:
                raise
            except Exception as error:  # pragma: no cover - provider-specific
                raise CvEmbeddingError(
                    "Unable to load Sentence Transformer model "
                    f"'{self._config.model_name}': {error}"
                ) from error

            actual_dimension = _get_model_embedding_dimension(self._model)
            if (
                actual_dimension is not None
                and actual_dimension != self._config.expected_dimension
            ):
                raise CvEmbeddingError(
                    "Embedding model dimension mismatch: expected "
                    f"{self._config.expected_dimension}, got {actual_dimension}."
                )
        return self._model

    def embed_chunks(
        self,
        chunks: Sequence[CvChunk],
    ) -> tuple[EmbeddedCvChunk, ...]:
        """Embed a deterministic chunk batch and validate every vector."""

        if not chunks:
            raise CvEmbeddingError("At least one CV chunk is required for embedding.")

        texts = [chunk.text for chunk in chunks]
        model = self.model
        try:
            raw_embeddings = model.encode(
                texts,
                batch_size=self._config.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=self._config.normalize_embeddings,
            )
        except Exception as error:  # pragma: no cover - provider-specific
            raise CvEmbeddingError(
                f"Sentence Transformer encoding failed: {error}"
            ) from error

        matrix = np.asarray(raw_embeddings, dtype=np.float32)
        expected_shape = (len(chunks), self._config.expected_dimension)
        if matrix.shape != expected_shape:
            raise CvEmbeddingError(
                "Embedding matrix shape mismatch: expected "
                f"{expected_shape}, got {matrix.shape}."
            )
        if not np.isfinite(matrix).all():
            raise CvEmbeddingError("Embedding matrix contains non-finite values.")

        if self._config.normalize_embeddings:
            norms = np.linalg.norm(matrix, axis=1)
            if not np.allclose(norms, 1.0, atol=1e-3):
                raise CvEmbeddingError(
                    "Normalized embeddings must have approximately unit length."
                )

        return tuple(
            EmbeddedCvChunk(
                chunk=chunk,
                embedding=tuple(float(value) for value in matrix[index]),
                embedding_model=self._config.model_name,
                embedding_dimension=self._config.expected_dimension,
                normalized=self._config.normalize_embeddings,
            )
            for index, chunk in enumerate(chunks)
        )

    def embed_texts(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        """Embed arbitrary query text using the same validated model contract."""

        if not texts or any(not text.strip() for text in texts):
            raise CvEmbeddingError("Embedding text values cannot be empty.")

        model = self.model
        try:
            raw_embeddings = model.encode(
                list(texts),
                batch_size=self._config.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=self._config.normalize_embeddings,
            )
        except Exception as error:  # pragma: no cover - provider-specific
            raise CvEmbeddingError(
                f"Sentence Transformer encoding failed: {error}"
            ) from error

        matrix = np.asarray(raw_embeddings, dtype=np.float32)
        expected_shape = (len(texts), self._config.expected_dimension)
        if matrix.shape != expected_shape or not np.isfinite(matrix).all():
            raise CvEmbeddingError(
                "Embedding provider returned an invalid query matrix: "
                f"expected {expected_shape}, got {matrix.shape}."
            )
        return tuple(
            tuple(float(value) for value in row)
            for row in matrix
        )


@lru_cache(maxsize=8)
def get_embedding_provider(
    model_name: str,
    expected_dimension: int,
    batch_size: int,
    normalize_embeddings: bool,
    device: str,
    cache_directory: Path,
) -> SentenceTransformerEmbeddingProvider:
    """Return one cached provider for one immutable embedding configuration."""

    return SentenceTransformerEmbeddingProvider(
        CvEmbeddingConfig(
            model_name=model_name,
            expected_dimension=expected_dimension,
            batch_size=batch_size,
            normalize_embeddings=normalize_embeddings,
            device=device,
            cache_directory=cache_directory,
        )
    )


def _get_model_embedding_dimension(
    model: SentenceTransformerModel,
) -> int | None:
    """Read the current Sentence Transformers dimension API safely.

    Sentence Transformers 5.4 renamed ``get_sentence_embedding_dimension``
    to ``get_embedding_dimension``. Prefer the current method so modern
    installations do not emit a deprecation warning, while retaining a
    narrow fallback for an already-instantiated older compatible model.
    """

    current_method = getattr(model, "get_embedding_dimension", None)
    if callable(current_method):
        return current_method()

    legacy_method = getattr(
        model,
        "get_sentence_embedding_dimension",
        None,
    )
    if callable(legacy_method):
        return legacy_method()

    return None


def _load_sentence_transformer_model(
    model_name: str,
    device: str,
    cache_directory: Path,
) -> SentenceTransformerModel:
    """Import Sentence Transformers lazily so non-RAG commands fail clearly."""

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as error:  # pragma: no cover - dependency boundary
        raise CvEmbeddingError(
            "sentence-transformers is not installed. Rebuild the backend image."
        ) from error

    return SentenceTransformer(
        model_name,
        device=device,
        cache_folder=str(cache_directory),
    )
