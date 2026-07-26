"""Keep every runnable backend command documented and discoverable."""

from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path

import pytest


SCRIPTS_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "scripts"
)
REFERENCE_PATH = SCRIPTS_DIRECTORY / "README.md"


def _is_runnable_module(path: Path) -> bool:
    """Return whether a Python file has an ``if __name__ == '__main__'`` entry."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not isinstance(test, ast.Compare) or len(test.ops) != 1:
            continue
        if not isinstance(test.left, ast.Name) or test.left.id != "__name__":
            continue
        if not isinstance(test.ops[0], ast.Eq) or len(test.comparators) != 1:
            continue
        comparator = test.comparators[0]
        if (
            isinstance(comparator, ast.Constant)
            and comparator.value == "__main__"
        ):
            return True
    return False


def _discover_runnable_script_modules() -> tuple[str, ...]:
    """Discover commands from source so a new script cannot miss help tests."""

    return tuple(
        path.stem
        for path in sorted(SCRIPTS_DIRECTORY.glob("*.py"))
        if _is_runnable_module(path)
    )


SCRIPT_MODULES = _discover_runnable_script_modules()


@pytest.mark.parametrize("script_name", SCRIPT_MODULES)
def test_every_runnable_script_has_complete_help(
    script_name: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Each command names every option, valid combinations, and side effects."""

    module = import_module(f"app.scripts.{script_name}")
    parser = module.build_parser()

    with pytest.raises(SystemExit) as exit_result:
        parser.parse_args(["--help"])

    assert exit_result.value.code == 0
    help_text = capsys.readouterr().out
    assert "usage:" in help_text
    assert "options:" in help_text
    assert "Valid command combinations:" in help_text
    assert "What the command changes:" in help_text
    assert "Example" in help_text

    # The normal argparse option list explains each flag. The combination
    # section must also name every long option so users can see where it is
    # valid and what other flags it can be combined with.
    combination_guide = parser.epilog or ""
    long_options = {
        option
        for action in parser._actions
        for option in action.option_strings
        if option.startswith("--") and option != "--help"
    }
    for option in long_options:
        assert option in combination_guide, (
            f"{script_name} does not mention {option} in its help sections"
        )


def test_central_command_reference_covers_every_script_and_option() -> None:
    """The central reference stays synchronized with discovered commands."""

    reference = REFERENCE_PATH.read_text(encoding="utf-8")

    assert SCRIPT_MODULES, "No runnable backend script modules were discovered."
    for script_name in SCRIPT_MODULES:
        module = import_module(f"app.scripts.{script_name}")
        parser = module.build_parser()

        assert f"`{script_name}`" in reference
        for action in parser._actions:
            for option in action.option_strings:
                if option.startswith("--") and option != "--help":
                    assert option in reference, (
                        f"The central reference is missing {script_name} {option}"
                    )
