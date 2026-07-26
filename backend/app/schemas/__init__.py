"""Public candidate schema imports.

Most backend modules import candidate types from ``app.schemas``. This file
keeps those imports short and hides the internal schema file layout.
"""

from .candidate import (
    CandidateProfile,
    Certification,
    ContactDetails,
    Education,
    Language,
    LanguageProficiency,
    ProfessionCategory,
    Project,
    SeniorityLevel,
    Skill,
    SkillCategory,
    WorkExperience,
)

# These names form the deliberate public interface of the schemas package.
__all__ = [
    "CandidateProfile",
    "Certification",
    "ContactDetails",
    "Education",
    "Language",
    "LanguageProficiency",
    "ProfessionCategory",
    "Project",
    "SeniorityLevel",
    "Skill",
    "SkillCategory",
    "WorkExperience",
]