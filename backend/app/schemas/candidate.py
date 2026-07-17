"""Candidate-profile schemas and controlled values.

These models define the structured data contract used when generating
fictional candidate profiles. Later, validated profiles will be rendered
into CV PDFs, but the RAG system will index only the generated PDFs.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Employment dates use year and month because CVs rarely need an exact day.
# The pattern accepts values such as "2022-01" but rejects invalid months.
YEAR_MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"

# Candidate IDs become stable links between the structured profile,
# candidate image, generated PDF, and later retrieval metadata.
CANDIDATE_ID_PATTERN = r"^candidate_\d{3}$"

class CandidateSchema(BaseModel):
    """Shared validation behaviour for all candidate-related models.

    Every candidate schema inherits these rules so we do not need to
    repeat the same Pydantic configuration in every nested model.
    """

    model_config = ConfigDict(
        # Remove accidental spaces such as "  Athens  " before validation.
        str_strip_whitespace=True,
        # Reject fields that are not part of our approved data contract.
        # This helps us detect unexpected keys in future LLM-generated JSON.
        extra="forbid",
    )


class ProfessionCategory(StrEnum):
    """Broad profession groups used to control dataset distribution.

    A candidate's exact CV title will remain more specific. For example,
    a candidate can belong to BACKEND_ENGINEERING while their professional
    title is "Senior Python Backend Engineer".
    """

    BACKEND_ENGINEERING = "backend_engineering"
    FRONTEND_ENGINEERING = "frontend_engineering"
    FULL_STACK_ENGINEERING = "full_stack_engineering"
    DATA_ENGINEERING = "data_engineering"
    DATA_SCIENCE = "data_science"
    MACHINE_LEARNING_ENGINEERING = "machine_learning_engineering"
    DEVOPS_CLOUD_ENGINEERING = "devops_cloud_engineering"
    QA_AUTOMATION = "qa_automation"
    PRODUCT_MANAGEMENT = "product_management"
    UX_UI_DESIGN = "ux_ui_design"


class SeniorityLevel(StrEnum):
    """Supported candidate seniority levels."""

    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"


class SkillCategory(StrEnum):
    """Groups individual skills into predictable CV sections."""

    PROGRAMMING_LANGUAGE = "programming_language"
    FRAMEWORK = "framework"
    DATABASE = "database"
    CLOUD = "cloud"
    DEVOPS = "devops"
    DATA_AI = "data_ai"
    TESTING = "testing"
    DESIGN = "design"
    PRODUCT = "product"
    OTHER = "other"


class LanguageProficiency(StrEnum):
    """Controlled proficiency levels for spoken languages."""

    NATIVE = "native"
    FLUENT = "fluent"
    PROFESSIONAL = "professional"
    INTERMEDIATE = "intermediate"
    BASIC = "basic"


class ContactDetails(CandidateSchema):
    """Contact and location information displayed on a candidate's CV."""

    # EmailStr validates that the generated value has a valid email structure.
    email: EmailStr

    # Phone formats vary internationally, so we apply sensible length limits
    # rather than using an overly restrictive country-specific pattern.
    phone: str = Field(min_length=7, max_length=25)

    city: str = Field(min_length=2, max_length=80)
    country: str = Field(min_length=2, max_length=80)


class Skill(CandidateSchema):
    """One professional skill belonging to a controlled category."""

    name: str = Field(min_length=1, max_length=80)
    category: SkillCategory

    # This value is optional because some CVs list a skill without claiming
    # an exact number of years. Zero is allowed for newly learned skills.
    years_of_experience: float | None = Field(
        default=None,
        ge=0,
        le=50,
    )


class Language(CandidateSchema):
    """One spoken language and the candidate's proficiency level."""

    name: str = Field(min_length=2, max_length=50)
    proficiency: LanguageProficiency


class WorkExperience(CandidateSchema):
    """One position in a candidate's professional history."""

    job_title: str = Field(min_length=2, max_length=120)
    company: str = Field(min_length=2, max_length=120)

    # Location is optional because remote roles may not have one clear city.
    location: str | None = Field(default=None, min_length=2, max_length=120)

    # Dates use the predictable YYYY-MM format, for example "2024-07".
    start_date: str = Field(pattern=YEAR_MONTH_PATTERN)

    # None means that the candidate is still working in this position.
    end_date: str | None = Field(
        default=None,
        pattern=YEAR_MONTH_PATTERN,
    )

    # These become bullet points in the rendered CV.
    # Limiting the count helps keep every PDF compact and readable.
    highlights: list[str] = Field(
        min_length=1,
        max_length=6,
    )

    # Technologies connect general skills to evidence from a real role.
    # An empty list is valid when a role is not technology-focused.
    technologies: list[str] = Field(
        default_factory=list,# This creates a new empty list for every model instance:
        max_length=15,
    )

    # This is present only when the role includes explicit people leadership.
    managed_team_size: int | None = Field(
        default=None,
        ge=1,
        le=100,
    )


class Education(CandidateSchema):
    """One education entry displayed in the candidate's CV."""

    degree: str = Field(min_length=2, max_length=120)
    field_of_study: str = Field(min_length=2, max_length=120)
    institution: str = Field(min_length=2, max_length=150)

    location: str | None = Field(
        default=None,
        min_length=2,
        max_length=120,
    )

    # Years are integers because month-level precision is usually unnecessary
    # for education sections in a CV.
    start_year: int = Field(
        ge=1980,
        le=2035,
    )

    # None means that the education program is still in progress.
    end_year: int | None = Field(
        default=None,
        ge=1980,
        le=2035,
    )

class Certification(CandidateSchema):
    """One professional certification listed on a candidate's CV."""

    name: str = Field(min_length=2, max_length=150)
    issuer: str = Field(min_length=2, max_length=120)

    # A year is enough for displaying and retrieving certification facts.
    year: int = Field(
        ge=1990,
        le=2035,
    )


class Project(CandidateSchema):
    """One professional or personal project shown on a candidate's CV."""

    name: str = Field(min_length=2, max_length=120)

    # The description should be short enough for predictable PDF rendering
    # while still containing useful evidence for later retrieval.
    description: str = Field(
        min_length=20,
        max_length=600,
    )

    # Project technologies provide searchable evidence, especially for
    # junior candidates with limited professional work history.
    technologies: list[str] = Field(
        min_length=1,
        max_length=15,
    )

    # The year is optional because some ongoing projects may not have one
    # meaningful completion year.
    year: int | None = Field(
        default=None,
        ge=1990,
        le=2035,
    )


class CandidateProfile(CandidateSchema):
    """Complete validated representation of one fictional candidate.

    The structured profile is used to generate a deterministic CV PDF.
    Later, the RAG pipeline will extract and index the PDF rather than
    reading this original structured object.
    """

    # Stable identifiers such as candidate_001 make filenames and metadata
    # predictable across profile generation, PDF rendering, and retrieval.
    candidate_id: str = Field(pattern=CANDIDATE_ID_PATTERN)

    full_name: str = Field(
        min_length=3,
        max_length=100,
    )

    # The exact title is more specific than the broad profession category.
    # Example: profession=backend_engineering while the title is
    # "Senior Python Backend Engineer".
    professional_title: str = Field(
        min_length=3,
        max_length=120,
    )

    profession: ProfessionCategory
    seniority: SeniorityLevel

    # Half-year values such as 4.5 are allowed.
    years_of_experience: float = Field(
        ge=0,
        le=50,
    )

    # The summary should contain enough useful evidence without becoming
    # too long for the top section of the generated CV.
    summary: str = Field(
        min_length=80,
        max_length=600,
    )

    contact: ContactDetails

    # Every candidate must have at least one employment entry.
    work_experience: list[WorkExperience] = Field(
        min_length=1,
        max_length=8,
    )

    # Education is allowed to be empty because professional experience or
    # vocational training may be more relevant for some candidates.
    education: list[Education] = Field(
        default_factory=list,
        max_length=4,
    )

    # At least three skills keep every profile useful for retrieval while
    # the upper limit protects the PDF from oversized skill sections.
    skills: list[Skill] = Field(
        min_length=3,
        max_length=30,
    )

    # Every candidate must have at least one spoken language.
    languages: list[Language] = Field(
        min_length=1,
        max_length=8,
    )

    # Empty lists make optional PDF sections easy to omit consistently.
    certifications: list[Certification] = Field(
        default_factory=list,
        max_length=8,
    )

    projects: list[Project] = Field(
        default_factory=list,
        max_length=6,
    )