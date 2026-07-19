"""Inspect local Hugging Face embeddings without writing ChromaDB records.

Examples:

    python -m app.scripts.inspect_cv_embeddings --file data/cv_pdfs/example.pdf
    python -m app.scripts.inspect_cv_embeddings --all --limit-chunks 10
"""

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

import numpy as np

from app.core.config import Settings, get_settings
from app.cv_ingestion import (
    CvChunkingConfig,
    CvChunkingError,
    CvDocumentExtractionError,
    CvDocumentSelectionError,
    CvEmbeddingConfig,
    CvEmbeddingError,
    SentenceTransformerEmbeddingProvider,
    chunk_cv_documents,
    get_embedding_provider,
    load_cv_documents,
    select_cv_pdf_paths,
)


def build_parser() -> argparse.ArgumentParser:
    """Create the developer command for extraction-to-embedding inspection."""

    parser = argparse.ArgumentParser(
        description=(
            "Extract, chunk, and embed selected CV PDFs without writing "
            "persistent vector records."
        )
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--file",
        action="append",
        type=Path,
        dest="files",
        help="Select one PDF. Repeat --file to inspect several PDFs.",
    )
    input_group.add_argument(
        "--directory",
        type=Path,
        help="Embed every PDF directly inside this directory.",
    )
    input_group.add_argument(
        "--all",
        action="store_true",
        dest="select_all",
        help="Embed every PDF in the configured default CV directory.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Include nested PDFs for --directory or --all.",
    )
    parser.add_argument(
        "--limit-chunks",
        type=int,
        help="Embed only the first N deterministic chunks for a quick smoke test.",
    )
    parser.add_argument(
        "--preview-vectors",
        type=int,
        default=3,
        help="Number of vector summaries to print (default: 3).",
    )
    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    provider: SentenceTransformerEmbeddingProvider | None = None,
) -> int:
    """Run PDF extraction, chunking, and local embedding inspection."""

    parser = build_parser()
    arguments = parser.parse_args(argv)
    active_settings = settings or get_settings()

    if arguments.limit_chunks is not None and arguments.limit_chunks < 1:
        print("ERROR: --limit-chunks must be positive.", file=sys.stderr)
        return 2
    if arguments.preview_vectors < 0:
        print("ERROR: --preview-vectors cannot be negative.", file=sys.stderr)
        return 2

    try:
        paths = select_cv_pdf_paths(
            files=tuple(arguments.files or ()),
            directory=arguments.directory,
            default_directory=active_settings.cv_ingestion_default_directory,
            select_all=arguments.select_all,
            recursive=arguments.recursive,
        )
        documents = load_cv_documents(paths)
        chunks = chunk_cv_documents(
            documents,
            config=CvChunkingConfig(
                version=active_settings.cv_chunking_version,
                max_characters=active_settings.cv_chunk_max_characters,
                min_characters=active_settings.cv_chunk_min_characters,
                overlap_characters=active_settings.cv_chunk_overlap_characters,
            ),
        )
        if arguments.limit_chunks is not None:
            chunks = chunks[: arguments.limit_chunks]

        active_provider = provider or get_embedding_provider(
            active_settings.cv_embedding_model_name,
            active_settings.cv_embedding_expected_dimension,
            active_settings.cv_embedding_batch_size,
            active_settings.cv_embedding_normalize,
            active_settings.cv_embedding_device,
            active_settings.cv_embedding_cache_directory,
        )
        embedded_chunks = active_provider.embed_chunks(chunks)
    except (
        CvDocumentSelectionError,
        CvDocumentExtractionError,
        CvChunkingError,
        CvEmbeddingError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    norms = [
        float(np.linalg.norm(np.asarray(item.embedding, dtype=np.float32)))
        for item in embedded_chunks
    ]
    print("CV EMBEDDING COMPLETE")
    print(f"  Documents: {len(documents)}")
    print(f"  Chunks embedded: {len(embedded_chunks)}")
    print(f"  Model: {active_provider.config.model_name}")
    print(f"  Dimension: {active_provider.config.expected_dimension}")
    print(f"  Batch size: {active_provider.config.batch_size}")
    print(f"  Normalized: {active_provider.config.normalize_embeddings}")
    print(f"  Vector norm range: {min(norms):.6f}-{max(norms):.6f}")

    preview_count = min(arguments.preview_vectors, len(embedded_chunks))
    if preview_count:
        print("\nVECTOR PREVIEW")
        for item in embedded_chunks[:preview_count]:
            first_values = ", ".join(
                f"{value:.5f}" for value in item.embedding[:5]
            )
            print(
                f"  {item.chunk.chunk_id} | "
                f"candidate={item.chunk.source.candidate_id} | "
                f"section={item.chunk.section_name} | "
                f"pages={item.chunk.page_label} | "
                f"values=[{first_values}, ...]"
            )
    return 0


def main() -> None:
    """Run the CLI and expose shell-friendly exit status."""

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
