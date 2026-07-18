"""Validate the normalized portrait subset defined by the coverage plan."""

from collections.abc import Collection, Sequence
from pathlib import Path

from app.schemas import CandidateProfile

from .images import PortraitImageError, inspect_portrait_image
from .models import PortraitCollectionValidation


_IMAGE_EXTENSIONS = {".jpeg", ".jpg", ".png", ".webp"}


def validate_portrait_collection(
    profiles: Sequence[CandidateProfile],
    *,
    portrait_candidate_ids: Collection[str],
    images_directory: Path,
    expected_size: int,
) -> PortraitCollectionValidation:
    """Verify every planned portrait exists and no unplanned images remain."""

    profile_ids = {
        profile.candidate_id
        for profile in profiles
    }
    expected_ids = set(portrait_candidate_ids)
    unknown_ids = expected_ids.difference(profile_ids)
    if unknown_ids:
        raise ValueError(
            "Portrait validation received unknown candidate IDs: "
            f"{', '.join(sorted(unknown_ids))}."
        )

    expected_paths = {
        candidate_id: images_directory / f"{candidate_id}.webp"
        for candidate_id in expected_ids
    }

    missing: list[str] = []
    invalid: list[str] = []
    valid_count = 0

    for candidate_id in sorted(expected_ids):
        path = expected_paths[candidate_id]
        if not path.is_file():
            missing.append(candidate_id)
            continue

        try:
            inspect_portrait_image(path, expected_size=expected_size)
        except PortraitImageError as error:
            invalid.append(f"{candidate_id}: {error}")
        else:
            valid_count += 1

    unexpected_files: list[str] = []
    if images_directory.exists():
        for path in sorted(images_directory.iterdir()):
            if not path.is_file() or path.name == ".gitkeep":
                continue
            if path.suffix.casefold() not in _IMAGE_EXTENSIONS:
                continue
            if path not in expected_paths.values():
                unexpected_files.append(path.name)

    return PortraitCollectionValidation(
        expected_count=len(expected_ids),
        valid_count=valid_count,
        missing_candidate_ids=tuple(missing),
        invalid_portraits=tuple(invalid),
        unexpected_files=tuple(unexpected_files),
    )
