# Candidate generation pipeline

## Summary explanation

This section turns one controlled candidate slot into one accepted
`CandidateProfile`, then builds the complete saved profile collection.

The language model proposes structured content. Python owns the acceptance
rules: schema validation, experience arithmetic, slot compliance, collection
uniqueness and persistence.

## Position in the complete application

### State before this section

- `candidate_dataset_plan.json` exists and describes the required 30 slots.
- `Settings` provides the plan path, output path, model and retry limits.
- No trusted generated profile is assumed yet.

### State after this section

- `data/candidate_profiles/candidate_profiles.json` contains sorted,
  schema-valid, slot-compliant candidate profiles.
- Those profiles can be used by portrait planning and CV rendering.
- The JSON is still not recruiter-answer evidence; the later PDF is.

```text
candidate_dataset_plan.json
-> CandidateDatasetPlan
-> selected CandidateGenerationSlot objects
-> OpenAI structured CandidateProfile
-> deterministic normalisation and validation
-> cross-candidate uniqueness check
-> atomic candidate_profiles.json save
```

## Actual entry point and coordinator

The normal command starts in:

```text
app.scripts.generate_candidate_profiles.run_cli()
```

The function that coordinates one candidate attempt loop is:

```text
candidate_generation.generation.generate_candidate_with_retries()
```

## Exact runtime order

### Collection-level command flow

```text
1. run_cli() reads command arguments.
2. get_settings() supplies paths, model and retry limits.
3. load_candidate_dataset_plan() reads and validates the committed plan.
4. select_candidate_slots() selects one, N, or all slots.
5. --dry-run stops here after printing the plan.
6. load_candidate_profiles() loads the existing collection for --resume.
7. create_openai_provider() builds OpenAICandidateGenerator only when work remains.
8. For each selected slot:
   a. build a uniqueness validator against profiles already accepted;
   b. call generate_candidate_with_retries();
   c. append the accepted profile;
   d. save_candidate_profiles() immediately.
9. Print generation totals and provider-attempt counts.
```

Saving after every accepted candidate makes `--resume` useful after an
interruption.

### One-candidate attempt flow

```text
generate_candidate_with_retries(slot)
-> provider.generate(slot, correction_feedback)
-> OpenAICandidateGenerator builds prompt and requests structured output
-> CandidateProfile schema validation
-> normalize_profile_experience(profile, slot)
-> validate_profile_against_slot(profile, slot)
-> additional uniqueness validators
-> accepted result
```

When deterministic validation finds correctable problems:

```text
problem list
-> correction_feedback
-> next provider attempt
```

When a provider timeout is retryable, the next attempt uses the base prompt
again because the failure says nothing about the candidate content.

## File map in execution order

| Runtime position | File | Responsibility |
|---:|---|---|
| 1 | [`models.py`](models.py) | Defines and validates `CandidateDatasetPlan`, `CandidateGenerationSlot` and planned fact models. |
| 2 | [`plan.py`](plan.py) | Loads the JSON plan and selects requested slots deterministically. |
| 3 | [`prompt.py`](prompt.py) | Converts one slot and optional correction feedback into provider instructions. |
| 4 | [`client.py`](client.py) | Calls OpenAI structured output and returns a schema-valid `CandidateProfile`. |
| 5 | [`generation.py`](generation.py) | Coordinates provider calls, bounded retries and all acceptance checks for one slot. |
| 6 | [`experience.py`](experience.py) | Makes employment dates and total experience arithmetically consistent. |
| 7 | [`compliance.py`](compliance.py) | Checks the accepted profile against every required slot fact. |
| 8 | [`uniqueness.py`](uniqueness.py) | Detects repeated identities and suspiciously identical work histories across profiles. |
| 9 | [`persistence.py`](persistence.py) | Loads, sorts and atomically writes the profile collection. |
| 10 | [`dataset_validation.py`](dataset_validation.py) | Validates the completed collection, distributions and planned search scenarios. |

`__init__.py` re-exports the package's public functions and types; it is not an
independent runtime stage.

## Important functions and classes

### `load_candidate_dataset_plan(path)`

Reads JSON, validates it through `CandidateDatasetPlan`, and raises a stable
plan error for missing, malformed or inconsistent data.

### `select_candidate_slots(...)`

Implements `--candidate-id`, `--count`, `--all` and `--start-from`. It returns a
stable ordered tuple so the same command selects the same slots.

### `build_candidate_prompt(slot, correction_feedback=())`

Builds the complete instructions for one candidate. The prompt contains the
slot's locked facts, output constraints and any deterministic problems from the
previous attempt.

### `OpenAICandidateGenerator.generate(...)`

Calls the configured OpenAI model with structured output. The result is parsed
as `CandidateProfile`, so malformed provider JSON cannot pass into later stages.

### `generate_candidate_with_retries(...)`

The central one-candidate coordinator. It never accepts provider output directly.
It applies this sequence on every attempt:

```text
provider -> experience normalisation -> slot compliance -> extra validators
```

### `normalize_profile_experience(profile, slot)`

Calculates non-overlapping employment months. When the slot contains a locked
experience total, it adjusts the timeline deterministically and rebuilds the
profile so displayed dates and `years_of_experience` agree.

Important helpers include:

- `calculate_non_overlapping_employment_months()`;
- `calculate_employment_years()`;
- `extract_locked_experience_years()`;
- `_rebuild_work_dates()`.

### `validate_profile_against_slot(profile, slot)`

Checks exact identity, required skills, language, education, certifications,
leadership facts, projects, explicit experience facts and date ordering.

### `find_profile_uniqueness_problems(profile, existing_profiles)`

Returns a problem list instead of immediately raising. That design allows
uniqueness failures to join the same provider correction loop.

### `save_candidate_profiles(path, profiles)`

Sorts by candidate ID and replaces the complete JSON file safely. The output
never depends on generation order.

### `validate_candidate_dataset(plan, profiles)`

Runs final collection checks: expected count, slot compliance, distributions,
uniqueness and search-scenario evidence.

## Why the profile is saved as JSON

The JSON file is the stable handoff between generation and rendering:

```text
hosted generation can stop
-> profiles remain locally reproducible
-> portrait and rendering commands can run without another profile-generation call
```

This also separates expensive data generation from deterministic document work.

## Failure and retry behavior

| Failure | Behavior |
|---|---|
| Invalid plan or CLI selection | Stop before any provider call. |
| Missing provider key | Stop before destructive overwrite. |
| Retryable provider failure | Retry within the configured limit. |
| Non-retryable provider failure | Fail that candidate immediately. |
| Experience/compliance/uniqueness problem | Send the full problem list as correction feedback. |
| Final attempt still invalid | Return `CandidateGenerationFailed`. |
| Save failure | Stop, because later candidates must not continue against an unsaved state. |

## Connection to the next sections

```text
candidate_profiles.json
├── portrait_generation uses profile identity and appearance plan
└── cv_rendering uses every profile fact to build the PDF
```

The complete profile collection should be validated before portraits or PDFs
are treated as final.

## Commands

```powershell
docker compose -p ai-cv-screener-openai exec backend `
  python -m app.scripts.generate_candidate_profiles --help

docker compose -p ai-cv-screener-openai exec backend `
  python -m app.scripts.validate_candidate_profiles --help
```

See [`../scripts/README.md`](../scripts/README.md) for all combinations and side
effects.

## Related tests

- `test_candidate_dataset_plan.py`
- `test_candidate_generation_plan.py`
- `test_candidate_generation_prompt.py`
- `test_openai_candidate_generator.py`
- `test_candidate_generation_service.py`
- `test_candidate_experience.py`
- `test_candidate_generation_compliance.py`
- `test_candidate_profile_uniqueness.py`
- `test_candidate_profile_persistence.py`
- `test_candidate_dataset_validation.py`
- `test_generate_candidate_profiles_cli.py`
