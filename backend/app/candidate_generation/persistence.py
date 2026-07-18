"""Safe JSON persistence for validated candidate profiles.

The generated profile file is preparation data for deterministic PDF rendering.
Only ``CandidateProfile`` instances may enter this module, and every existing
file is validated again when it is loaded. Atomic replacement prevents a
partially written JSON document if generation is interrupted during a save.
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
    """Load and validate previously accepted profiles.

    A missing file represents an empty dataset. Existing malformed files fail
    loudly so ``--resume`` never builds new results on top of corrupted data.
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
    """Atomically persist validated profiles in stable candidate-ID order.

    The temporary file is created beside the destination so ``os.replace`` is
    an atomic operation on the same filesystem. ``flush`` and ``fsync`` push
    buffered content before the final replacement.
    """

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
