"""Shared formatting helpers for the backend command-line tools.

Every script uses the same readable help layout. The normal argument list stays
inside the script that owns the command, while this module only formats the
extra sections that explain valid combinations, side effects, and examples.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence


HelpSection = tuple[str, Sequence[str]]


def build_cli_parser(
    *,
    description: str,
    sections: Sequence[HelpSection],
) -> argparse.ArgumentParser:
    """Create an ``ArgumentParser`` with consistent multi-section help text."""

    return argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_format_sections(sections),
    )


def _format_sections(sections: Sequence[HelpSection]) -> str:
    """Turn titled help sections into an indented argparse epilog."""

    rendered_sections: list[str] = []
    for title, lines in sections:
        body = "\n".join(f"  {line}" if line else "" for line in lines)
        rendered_sections.append(f"{title}:\n{body}")
    return "\n\n".join(rendered_sections)
