"""Load and save the validated candidate profile collection.

The JSON file is preparation data for CV rendering. Every loaded record is
validated again as ``CandidateProfile``. Saves use a temporary file followed by
an atomic replacement, so an interruption cannot leave half-written JSON.
Profiles are always written in candidate-ID order to keep resume and review
behaviour predictable.
"""

from json import JSONDecodeError, dumps, loads
from os import fsync, replace
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import TypeAdapter, ValidationError

from app.schemas import CandidateProfile


# TypeAdapter validates the complete JSON array in one operation. This keeps
# top-level parsing rules in one reusable object instead of validating every
# dictionary manually throughout the application.
_PROFILE_LIST_ADAPTER = TypeAdapter(list[CandidateProfile])


class CandidateProfilesFileError(RuntimeError):
    """Raised when the generated profile file cannot be read or written."""


def load_candidate_profiles(path: Path) -> list[CandidateProfile]:
    """Load, validate, and sort the saved candidate profiles.
    
    A missing file means generation has not started and returns an empty list. A
    present but invalid file raises a clear error rather than letting bad data reach
    CV rendering.
    """

    if not path.exists():
        return []

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise CandidateProfilesFileError(
            f"Candidate profiles could not be read: {path}"
        ) from error

    try:
        raw_profiles = loads(raw_text)
    except JSONDecodeError as error:
        raise CandidateProfilesFileError(
            f"Candidate profiles contain invalid JSON: {path}"
        ) from error

    try:
        profiles = _PROFILE_LIST_ADAPTER.validate_python(raw_profiles)
    except ValidationError as error:
        raise CandidateProfilesFileError(
            f"Candidate profiles failed validation: {path}\n{error}"
        ) from error

    return _sort_profiles(profiles)


def save_candidate_profiles(
    path: Path,
    profiles: list[CandidateProfile],
) -> None:
    """Validate ordering and atomically save the complete profile collection."""

    ordered_profiles = _sort_profiles(profiles)
    serialized_profiles = dumps(
        [
            profile.model_dump(mode="json")
            for profile in ordered_profiles
        ],
        ensure_ascii=False,
        indent=2,
    ) + "\n"

    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(serialized_profiles)
            temporary_file.flush()
            fsync(temporary_file.fileno())

        replace(temporary_path, path)
    except OSError as error:
        # NamedTemporaryFile may have succeeded before a later operation
        # failed. Remove that leftover file without hiding the original error.
        if "temporary_path" in locals():
            temporary_path.unlink(missing_ok=True)

        raise CandidateProfilesFileError(
            f"Candidate profiles could not be written: {path}"
        ) from error


def _sort_profiles(
    profiles: list[CandidateProfile],
) -> list[CandidateProfile]:
    """Return a new list in deterministic candidate-plan order."""

    return sorted(profiles, key=lambda profile: profile.candidate_id)
