# Candidate profile schemas

## Summary explanation

This section defines the trusted shape of one fictional candidate. The schema is
the first gate between untrusted generated content and the rest of the document
pipeline.

```text
Provider JSON or saved JSON
-> Pydantic nested models
-> field and cross-field validation
-> trusted CandidateProfile
-> generation compliance checks
-> persistence and PDF rendering
```

A profile can continue only after all structural schema rules pass.

## Position in the architecture

Before this section, candidate data may be raw provider output or JSON loaded
from disk. After this section, the application has typed objects with valid
enums, dates, positive durations, required text and duplicate protection.

The schema answers:

> Is this internally valid candidate data?

The generation compliance layer answers a different question:

> Does this valid profile satisfy the exact facts required by its planned slot?

## Files

| File | Runtime role |
|---|---|
| [`candidate.py`](candidate.py) | Defines all enums, nested candidate models and cross-field validators. |
| [`__init__.py`](__init__.py) | Re-exports the public schema types used throughout the backend. |

## Object construction order

When `CandidateProfile.model_validate(...)` receives provider or file data,
Pydantic validates nested objects from the inside out:

```text
primitive values
-> enums and simple nested models
-> WorkExperience / Education / Project checks
-> CandidateProfile collection checks
-> complete CandidateProfile instance
```

The main model tree is:

```text
CandidateProfile
├── ContactDetails
├── list[Skill]
├── list[Language]
├── list[WorkExperience]
├── list[Education]
├── list[Certification]
└── list[Project]
```

## Important models

### `CandidateProfile`

The root model used by generation, persistence, portrait planning and rendering.
Important fields include candidate identity, title, summary, total experience,
skills, languages, employment, education, certifications and projects.

Important validators:

- `validate_unique_skills()` prevents duplicate skill names;
- `validate_unique_languages()` prevents duplicate language entries;
- `validate_profile_consistency()` checks profile-level relationships and repeated data.

### `WorkExperience`

Represents one employment interval. Important validators:

- `validate_unique_technologies()` prevents repeated technologies inside one role;
- `validate_date_order()` rejects end dates earlier than start dates.

The later experience-normalisation section may adjust valid date ranges to make
the complete timeline match a locked experience total.

### `Education`

`validate_year_order()` ensures the graduation/end year is not before the start
year.

### `Project`

`validate_unique_technologies()` keeps the project technology list meaningful
and non-repetitive.

### Enums

`ProfessionCategory`, `SeniorityLevel`, `SkillCategory`,
`LanguageProficiency` and related enums constrain free-form generated text to
known values used by planning, validation, formatting and retrieval tests.

## Where the schema is used

```text
candidate_generation/client.py
    OpenAI structured output -> CandidateProfile

candidate_generation/persistence.py
    saved JSON -> list[CandidateProfile]

portrait_generation/planning.py
    CandidateProfile -> PortraitGenerationJob

cv_rendering/planning.py
    CandidateProfile -> CvRenderJob

candidate_generation/dataset_validation.py
    list[CandidateProfile] -> collection validation report
```

## Important boundary

The schema does not prove:

- that a profile matches its assigned dataset slot;
- that total experience agrees with all employment intervals;
- that profiles are unique across the complete collection;
- that a rendered PDF preserves every expected fact;
- that recruiter answers are supported.

Those responsibilities belong to later sections. This keeps the schema focused
on reusable structural integrity.

## Main command

```powershell
docker compose -p ai-cv-screener-openai exec backend `
  python -m app.scripts.validate_candidate_schema --help
```

## Related tests

- `tests/test_candidate_schemas.py`
- `tests/test_candidate_generation_compliance.py`
- `tests/test_candidate_experience.py`
- `tests/test_candidate_profile_persistence.py`
