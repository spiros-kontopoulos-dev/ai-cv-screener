"""Load and validate the committed candidate portrait coverage plan.

The assignment asks for realistic CVs that include AI-generated photography,
but it does not require every CV to use the same visual convention. This plan
makes the mixed dataset deliberate: selected candidates receive generated
portraits and the remaining candidates use an intentional photo-free layout.

Portrait appearance descriptors are explicit plan data. They describe only the
fictional image presentation that should be generated; they are not inferred
from a candidate name, nationality, or any real person's identity.
"""

from collections.abc import Sequence
from json import JSONDecodeError, loads
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.schemas import CandidateProfile
from app.schemas.candidate import CANDIDATE_ID_PATTERN


CandidateId = Annotated[str, Field(pattern=CANDIDATE_ID_PATTERN)]
PortraitPresentation = Literal[
    "masculine-presenting",
    "feminine-presenting",
    "androgynous-presenting",
]


class PortraitCoveragePlanError(RuntimeError):
    """Raised when the committed portrait plan is missing or inconsistent."""


class PortraitAppearance(BaseModel):
    """One explicit fictional appearance contract for a portrait candidate."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    candidate_id: CandidateId
    presentation: PortraitPresentation
    visual_description: str = Field(min_length=20, max_length=300)


class PortraitCoveragePlan(BaseModel):
    """Strict contract for the controlled photo and photo-free CV split."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    plan_version: int = Field(ge=1)
    portrait_count: int = Field(ge=1, le=100)
    purpose: str = Field(min_length=20, max_length=500)
    selection_strategy: str = Field(min_length=20, max_length=500)
    portrait_candidate_ids: list[CandidateId] = Field(min_length=1)
    portrait_appearances: list[PortraitAppearance] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_internal_consistency(self) -> Self:
        """Keep count, ordered IDs, and appearance descriptors aligned."""

        if self.portrait_count != len(self.portrait_candidate_ids):
            raise ValueError(
                "portrait_count must match portrait_candidate_ids."
            )

        if len(self.portrait_candidate_ids) != len(
            set(self.portrait_candidate_ids)
        ):
            raise ValueError(
                "portrait_candidate_ids must not contain duplicates."
            )

        if self.portrait_candidate_ids != sorted(
            self.portrait_candidate_ids
        ):
            raise ValueError(
                "portrait_candidate_ids must be ordered by candidate ID."
            )

        appearance_ids = [
            appearance.candidate_id
            for appearance in self.portrait_appearances
        ]
        if appearance_ids != sorted(appearance_ids):
            raise ValueError(
                "portrait_appearances must be ordered by candidate ID."
            )

        if len(appearance_ids) != len(set(appearance_ids)):
            raise ValueError(
                "portrait_appearances must not contain duplicate candidate IDs."
            )

        if set(appearance_ids) != set(self.portrait_candidate_ids):
            raise ValueError(
                "portrait_appearances must describe every portrait candidate "
                "exactly once."
            )

        return self

    @property
    def portrait_candidate_id_set(self) -> frozenset[str]:
        """Return the planned portrait IDs as an immutable lookup set."""

        return frozenset(self.portrait_candidate_ids)

    @property
    def appearance_by_candidate_id(self) -> dict[str, PortraitAppearance]:
        """Return the explicit appearance contract keyed by candidate ID."""

        return {
            appearance.candidate_id: appearance
            for appearance in self.portrait_appearances
        }


def load_portrait_coverage_plan(path: Path) -> PortraitCoveragePlan:
    """Read and validate the committed portrait coverage JSON file."""

    try:
        raw_text = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise PortraitCoveragePlanError(
            f"Candidate portrait plan was not found: {path}"
        ) from error
    except OSError as error:
        raise PortraitCoveragePlanError(
            f"Candidate portrait plan could not be read: {path}"
        ) from error

    try:
        raw_plan = loads(raw_text)
    except JSONDecodeError as error:
        raise PortraitCoveragePlanError(
            f"Candidate portrait plan contains invalid JSON: {path}"
        ) from error

    try:
        return PortraitCoveragePlan.model_validate(raw_plan)
    except ValidationError as error:
        raise PortraitCoveragePlanError(
            f"Candidate portrait plan failed validation: {path}\n{error}"
        ) from error


def validate_portrait_coverage_against_profiles(
    plan: PortraitCoveragePlan,
    profiles: Sequence[CandidateProfile],
) -> None:
    """Ensure the coverage plan references the current profile collection."""

    profile_ids = [profile.candidate_id for profile in profiles]
    if len(profile_ids) != len(set(profile_ids)):
        raise PortraitCoveragePlanError(
            "Candidate profiles contain duplicate candidate IDs."
        )

    unknown_ids = plan.portrait_candidate_id_set.difference(profile_ids)
    if unknown_ids:
        raise PortraitCoveragePlanError(
            "Candidate portrait plan contains unknown candidate IDs: "
            f"{', '.join(sorted(unknown_ids))}."
        )
