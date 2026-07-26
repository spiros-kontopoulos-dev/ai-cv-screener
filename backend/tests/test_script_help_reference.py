"""Keep backend command help complete and discoverable."""

from importlib import import_module
from pathlib import Path

import pytest


SCRIPT_MODULES = (
    "evaluate_cv_query_robustness",
    "generate_candidate_portraits",
    "generate_candidate_profiles",
    "ingest_cv_documents",
    "inspect_assisted_cv_retrieval",
    "inspect_candidate_cv_retrieval",
    "inspect_cv_chunks",
    "inspect_cv_documents",
    "inspect_cv_embeddings",
    "inspect_cv_vector_store",
    "inspect_final_cv_retrieval",
    "inspect_grounded_cv_answer",
    "inspect_raw_cv_retrieval",
    "rename_cv_documents",
    "render_candidate_cvs",
    "smoke_test_cv_index",
    "validate_candidate_cvs",
    "validate_candidate_portraits",
    "validate_candidate_profiles",
    "validate_candidate_schema",
    "validate_cv_retrieval",
)


@pytest.mark.parametrize("script_name", SCRIPT_MODULES)
def test_script_help_explains_combinations_and_side_effects(
    script_name: str,
) -> None:
    """Every runnable module exposes arguments, combinations, and safety notes."""

    module = import_module(f"app.scripts.{script_name}")
    help_text = module.build_parser().format_help()

    assert "usage:" in help_text
    assert "Valid command combinations:" in help_text
    assert "What the command changes:" in help_text
    assert "Example" in help_text


def test_central_command_reference_lists_every_script() -> None:
    """The package reference remains synchronized with runnable modules."""

    reference_path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "scripts"
        / "README.md"
    )
    reference = reference_path.read_text(encoding="utf-8")

    for script_name in SCRIPT_MODULES:
        assert f"`{script_name}`" in reference
