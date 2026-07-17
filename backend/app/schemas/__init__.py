"""Public imports for the application's Pydantic schemas.

Other application modules can import these types directly from
``app.schemas`` without knowing which internal file defines them.
"""

from .candidate import (
    ContactDetails,
    Language,
    LanguageProficiency,
    ProfessionCategory,
    SeniorityLevel,
    Skill,
    SkillCategory,
)

# These names form the deliberate public interface of the schemas package.
__all__ = [
    "ContactDetails",
    "Language",
    "LanguageProficiency",
    "ProfessionCategory",
    "SeniorityLevel",
    "Skill",
    "SkillCategory",
]