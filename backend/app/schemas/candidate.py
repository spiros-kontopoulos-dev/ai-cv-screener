"""Candidate-profile schemas and controlled values.

These models define the structured data contract used when generating
fictional candidate profiles. Later, validated profiles will be rendered
into CV PDFs, but the RAG system will index only the generated PDFs.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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