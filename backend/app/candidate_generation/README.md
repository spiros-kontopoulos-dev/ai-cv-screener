# Candidate generation

## Summary explanation

This section creates a controlled collection of fictional candidate profiles.
The language model proposes structured content, but deterministic Python rules
validate identity, required facts, experience duration, uniqueness, and complete
dataset coverage before anything is saved.

```text
candidate_dataset_plan.json
-> selected candidate slot
-> structured generation prompt
-> OpenAI structured response
-> deterministic normalisation and validation
-> candidate_profiles.json
```

The generated profile JSON is used to render the CV documents. It is not used as
the evidence source for recruiter answers; the indexed PDF CVs are the source of
truth.

## Files

| File | Purpose |
|---|---|
| [`models.py`](models.py) | Pydantic models for generation slots, planned facts, search scenarios, and the complete dataset plan. |
| [`plan.py`](plan.py) | Loads the committed plan and selects one, several, or all candidate slots. |
| [`prompt.py`](prompt.py) | Builds precise instructions for one fictional candidate. |
| [`client.py`](client.py) | Calls OpenAI structured output and parses one `CandidateProfile`. |
| [`generation.py`](generation.py) | Coordinates bounded retries, normalisation, compliance, and uniqueness checks. |
| [`experience.py`](experience.py) | Calculates non-overlapping employment duration and corrects inconsistent model arithmetic. |
| [`compliance.py`](compliance.py) | Proves that a profile satisfies the exact requirements of its planned slot. |
| [`uniqueness.py`](uniqueness.py) | Detects clear duplicate identities and work-history signatures. |
| [`persistence.py`](persistence.py) | Loads, sorts, and atomically saves the candidate profile collection. |
| [`dataset_validation.py`](dataset_validation.py) | Validates the final 30-profile collection, distributions, uniqueness, and planned search scenarios. |

## Why experience is recalculated

A model can produce realistic dates but state the wrong total number of years.
`experience.py` converts every employment range into months, merges overlapping
ranges, and calculates the total in Python. This keeps the final profile and PDF
internally consistent.

## Main commands

Display all options:

```powershell
docker compose exec backend python -m app.scripts.generate_candidate_profiles --help
```

Validate the saved collection:

```powershell
docker compose exec backend python -m app.scripts.validate_candidate_profiles --help
```

The complete argument combinations and side effects are documented in
[`../scripts/README.md`](../scripts/README.md).

## Related tests

The main tests are named `test_candidate_*`,
`test_openai_candidate_generator.py`, and
`test_generate_candidate_profiles_cli.py` under `backend/tests`.
