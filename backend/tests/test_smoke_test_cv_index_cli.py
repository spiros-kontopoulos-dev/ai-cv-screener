"""CLI tests for raw semantic Chroma smoke queries."""

from app.cv_ingestion import RawVectorMatch, VectorCollectionInfo
from app.scripts.smoke_test_cv_index import run_cli


class FakeProvider:
    def embed_texts(self, texts):
        return tuple((1.0, 0.0, 0.0, 0.0) for _ in texts)


class FakeRepository:
    def get_collection_info(self):
        return VectorCollectionInfo(
            collection_name="cv_chunks",
            record_count=184,
            metadata={},
            distance_metric="cosine",
        )

    def query_nearest(self, vector, *, n_results):
        return (
            RawVectorMatch(
                chunk_id="chunk_1",
                distance=0.12,
                text="Built Python and FastAPI services.",
                metadata={
                    "candidate_id": "candidate_001",
                    "candidate_name": "Jane Example",
                    "section_name": "experience",
                    "page_numbers": "1",
                    "source_filename": "jane.pdf",
                },
            ),
        )


def test_cli_prints_raw_semantic_matches(capsys) -> None:
    """Smoke output remains raw and traceable without candidate-aware ranking."""

    exit_code = run_cli(
        ["--query", "Who knows Python?", "--top-k", "3"],
        provider=FakeProvider(),
        repository=FakeRepository(),
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "RAW CV INDEX SMOKE TEST" in output
    assert "QUERY: Who knows Python?" in output
    assert "candidate=candidate_001" in output
    assert "distance=0.120000" in output
    assert "Built Python and FastAPI services" in output


def test_cli_rejects_invalid_top_k(capsys) -> None:
    """Invalid raw query limits fail before model or Chroma access."""

    exit_code = run_cli(
        ["--query", "Python", "--top-k", "0"],
        provider=FakeProvider(),
        repository=FakeRepository(),
    )

    assert exit_code == 2
    assert "must be positive" in capsys.readouterr().err
