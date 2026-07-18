"""Typed contracts for the controlled candidate dataset plan."""

from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas import LanguageProficiency, ProfessionCategory, SeniorityLevel
from app.schemas.candidate import CANDIDATE_ID_PATTERN


CandidateId = Annotated[str, Field(pattern=CANDIDATE_ID_PATTERN)]


class GenerationPlanSchema(BaseModel):
    """Shared strict behaviour for dataset-plan models."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )


class PlannedLanguage(GenerationPlanSchema):
    """One required spoken language in a candidate plan slot."""

    name: str = Field(min_length=2, max_length=50)
    proficiency: LanguageProficiency


class PlannedCertification(GenerationPlanSchema):
    """A certification that the generated profile must contain."""

    name: str = Field(min_length=2, max_length=150)
    issuer: str = Field(min_length=2, max_length=120)
    year: int = Field(ge=1990, le=2035)


class PlannedEducation(GenerationPlanSchema):
    """Education evidence required for a controlled retrieval scenario."""

    degree: str = Field(min_length=2, max_length=120)
    field_of_study: str = Field(min_length=2, max_length=120)
    institution: str = Field(min_length=2, max_length=150)


class PlannedProject(GenerationPlanSchema):
    """A portfolio project that must appear in the generated profile."""

    name: str = Field(min_length=2, max_length=120)
    technologies: list[str] = Field(min_length=1, max_length=15)


class CandidateGenerationSlot(GenerationPlanSchema):
    """Deterministic requirements for generating one fictional candidate."""

    candidate_id: CandidateId
    full_name: str = Field(min_length=3, max_length=100)
    professional_title: str = Field(min_length=3, max_length=120)
    profession: ProfessionCategory
    seniority: SeniorityLevel
    country: str = Field(min_length=2, max_length=80)
    city: str = Field(min_length=2, max_length=80)
    languages: list[PlannedLanguage] = Field(min_length=1, max_length=8)
    required_skills: list[str] = Field(min_length=5, max_length=30)
    certification: PlannedCertification | None = None
    leadership_team_size: int | None = Field(default=None, ge=1, le=100)
    required_education: PlannedEducation | None = None
    required_project: PlannedProject | None = None
    known_facts: list[str] = Field(min_length=3, max_length=12)
    demo_tags: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_unique_slot_values(self) -> Self:
        """Reject duplicate constraints that could confuse prompt generation."""

        _ensure_case_insensitive_unique(
            self.required_skills,
            field_name="required_skills",
        )
        _ensure_case_insensitive_unique(
            [language.name for language in self.languages],
            field_name="languages",
        )
        _ensure_case_insensitive_unique(
            self.demo_tags,
            field_name="demo_tags",
        )

        if self.required_project is not None:
            _ensure_case_insensitive_unique(
                self.required_project.technologies,
                field_name="required_project.technologies",
            )

        return self


class SearchScenario(GenerationPlanSchema):
    """A known question used later to verify retrieval and grounding."""

    scenario_id: str = Field(min_length=3, max_length=100)
    question: str = Field(min_length=5, max_length=500)
    expected_candidate_ids: list[CandidateId]

    # Unsupported questions intentionally contain no supporting evidence.
    required_evidence: list[str] = Field(default_factory=list, max_length=20)
    answer_behavior: str = Field(min_length=5, max_length=500)


class CandidateDatasetPlan(GenerationPlanSchema):
    """Validated top-level contract for the synthetic dataset plan."""

    dataset_version: int = Field(ge=1)
    candidate_count: int = Field(ge=1, le=100)
    purpose: str = Field(min_length=10, max_length=500)
    fictional_data_policy: dict[str, bool] = Field(min_length=1)
    generation_rules: dict[str, bool | str] = Field(min_length=1)

    # Distribution summaries are already verified by the existing WP2 tests.
    # The generator only needs to preserve them as plan metadata.
    distributions: dict[str, Any] = Field(min_length=1)

    search_scenarios: list[SearchScenario] = Field(min_length=1)
    candidates: list[CandidateGenerationSlot] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_plan_consistency(self) -> Self:
        """Ensure counts, identifiers, policies, and scenarios agree."""

        if self.candidate_count != len(self.candidates):
            raise ValueError(
                "candidate_count must match the number of candidate slots."
            )

        candidate_ids = [slot.candidate_id for slot in self.candidates]
        expected_ids = [
            f"candidate_{number:03d}"
            for number in range(1, self.candidate_count + 1)
        ]

        if candidate_ids != expected_ids:
            raise ValueError(
                "Candidate slots must be ordered sequentially from "
                "candidate_001."
            )

        _ensure_case_insensitive_unique(
            [slot.full_name for slot in self.candidates],
            field_name="candidate full names",
        )
        _ensure_case_insensitive_unique(
            [scenario.scenario_id for scenario in self.search_scenarios],
            field_name="search scenario IDs",
        )

        disabled_policies = [
            name
            for name, enabled in self.fictional_data_policy.items()
            if not enabled
        ]
        if disabled_policies:
            raise ValueError(
                "All fictional-data policies must remain enabled: "
                f"{', '.join(sorted(disabled_policies))}."
            )

        valid_candidate_ids = set(candidate_ids)
        for scenario in self.search_scenarios:
            unknown_ids = set(scenario.expected_candidate_ids).difference(
                valid_candidate_ids
            )
            if unknown_ids:
                raise ValueError(
                    f"Search scenario {scenario.scenario_id!r} references "
                    "unknown candidate IDs: "
                    f"{', '.join(sorted(unknown_ids))}."
                )

        return self


def _ensure_case_insensitive_unique(
    values: list[str],
    *,
    field_name: str,
) -> None:
    """Raise a deterministic validation error for repeated text values."""

    normalized_values = [value.casefold() for value in values]
    if len(normalized_values) != len(set(normalized_values)):
        raise ValueError(f"{field_name} must not contain duplicate values.")
