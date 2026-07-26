# Candidate schemas

## Summary explanation

This section defines the trusted structure of one fictional candidate profile.
All generated candidate data must pass these Pydantic rules before it can be
saved, rendered, or used to build the PDF corpus.

## Files

| File | Purpose |
|---|---|
| [`candidate.py`](candidate.py) | Enums and nested models for contact details, skills, languages, work history, education, certifications, projects, and the complete candidate profile. |
| [`__init__.py`](__init__.py) | Exposes the public schema types used by the rest of the backend. |

## Main validation rules

The models check, among other things:

- required text and valid enum values;
- positive experience and skill durations;
- valid work and education date ranges;
- minimum descriptions and highlights;
- no duplicate skill, language, company, or degree entries where uniqueness is
  required;
- a complete candidate identity and searchable professional history.

These structural rules are different from dataset-slot compliance. The schema
answers “is this a valid candidate profile?” while
`candidate_generation/compliance.py` answers “does this profile satisfy the
specific controlled slot it was generated for?”

## Main command

```powershell
docker compose exec backend python -m app.scripts.validate_candidate_schema --help
```

## Related tests

- `tests/test_candidate_schemas.py`
- `tests/test_candidate_generation_compliance.py`
