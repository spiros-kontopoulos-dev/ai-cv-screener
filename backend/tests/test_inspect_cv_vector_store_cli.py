"""CLI tests for persistent Chroma collection inspection."""

from app.cv_ingestion import VectorCollectionInfo
from app.scripts.inspect_cv_vector_store import run_cli


class FakeRepository:
    """Return one deterministic collection summary without opening Chroma."""

    def get_collection_info(self) -> VectorCollectionInfo:
        return VectorCollectionInfo(
            collection_name="cv_chunks",
            record_count=184,
            metadata={
                "embedding_model": "test-model",
                "embedding_dimension": 4,
                "chunking_version": "cv-sections-v1",
                "index_version": "cv-index-v1",
                "distance_metric": "cosine",
            },
            distance_metric="cosine",
        )


def test_cli_prints_collection_count_and_compatibility_metadata(capsys) -> None:
    """The inspection command exposes the persisted collection contract."""

    exit_code = run_cli(repository=FakeRepository())
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "CV VECTOR COLLECTION" in output
    assert "Name: cv_chunks" in output
    assert "Records: 184" in output
    assert "Distance metric: cosine" in output
    assert "embedding_model: test-model" in output


def test_cli_rejects_unexpected_arguments(capsys) -> None:
    """The read-only command has no hidden mutation or selection arguments."""

    exit_code = run_cli(["--reset"], repository=FakeRepository())

    assert exit_code == 2
    assert "does not accept arguments" in capsys.readouterr().err
