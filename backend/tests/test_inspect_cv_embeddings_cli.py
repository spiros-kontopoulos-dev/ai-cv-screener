"""CLI tests for extraction-to-embedding inspection."""

from pathlib import Path

import numpy as np
import pymupdf

from app.core.config import Settings
from app.cv_ingestion import (
    CvEmbeddingConfig,
    SentenceTransformerEmbeddingProvider,
)
from app.scripts.inspect_cv_embeddings import run_cli


class FakeModel:
    def get_sentence_embedding_dimension(self) -> int:
        return 4

    def encode(self, sentences, **kwargs):
        matrix = np.ones((len(sentences), 4), dtype=np.float32)
        return matrix / np.linalg.norm(matrix, axis=1, keepdims=True)


def test_cli_embeds_selected_pdf_and_prints_vector_contract(
    tmp_path: Path,
    capsys,
) -> None:
    """The CLI reports model, dimension, norm, and stable chunk identity."""

    pdf_path = tmp_path / "candidate_001.pdf"
    _write_pdf(
        pdf_path,
        "Jane Example\nBackend Engineer\nPROFESSIONAL PROFILE\nBuilds APIs.\n"
        "SKILLS\nPython FastAPI",
    )
    provider = SentenceTransformerEmbeddingProvider(
        CvEmbeddingConfig(
            model_name="test-model",
            expected_dimension=4,
            batch_size=2,
            cache_directory=tmp_path / "models",
        ),
        model_loader=lambda *_: FakeModel(),
    )

    exit_code = run_cli(
        ["--file", str(pdf_path), "--preview-vectors", "1"],
        settings=Settings(
            cv_embedding_model_name="test-model",
            cv_embedding_expected_dimension=4,
            cv_embedding_cache_directory=tmp_path / "models",
        ),
        provider=provider,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "CV EMBEDDING COMPLETE" in output
    assert "Model: test-model" in output
    assert "Dimension: 4" in output
    assert "Vector norm range: 1.000000-1.000000" in output
    assert "candidate=candidate_001" in output


def test_cli_rejects_invalid_chunk_limit(capsys) -> None:
    """Invalid smoke-test limits fail before model loading."""

    exit_code = run_cli(["--all", "--limit-chunks", "0"])

    assert exit_code == 2
    assert "must be positive" in capsys.readouterr().err


def _write_pdf(path: Path, text: str) -> None:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()
