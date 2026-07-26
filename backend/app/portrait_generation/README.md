# Portrait generation pipeline

## Summary explanation

This section creates the planned fictional candidate portraits. It does not add
a portrait to every profile. The committed coverage plan determines which
candidate IDs receive portraits and which remain intentionally photo-free.

Provider output is never used directly. Every image is decoded, cropped,
resized, converted to WebP and inspected before it becomes a rendering input.

## Position in the complete application

### State before this section

- validated `candidate_profiles.json` exists;
- `candidate_portrait_plan.json` identifies portrait and photo-free candidates;
- the image output directory may be empty or partially complete.

### State after this section

- each planned candidate has `data/candidate_images/candidate_ID.webp`;
- each file has a stable format and size;
- coverage validation proves that planned and photo-free states agree;
- CV rendering can safely connect candidate IDs to images.

```text
CandidateProfile collection + portrait plan
-> validated coverage
-> deterministic PortraitGenerationJob objects
-> text-free portrait prompt
-> OpenAI image bytes
-> normalised WebP
-> collection validation
```

## Entry point and coordinator

The normal command starts in:

```text
app.scripts.generate_candidate_portraits.run_cli()
```

One image job is coordinated by:

```text
portrait_generation.generation.generate_portrait_with_retries()
```

## Exact runtime order

```text
1. run_cli() parses selection, dry-run and overwrite arguments.
2. get_settings() supplies profile, plan, output and provider settings.
3. load_candidate_profiles() loads trusted CandidateProfile objects.
4. load_portrait_coverage_plan() validates the committed plan.
5. validate_portrait_coverage_against_profiles() proves candidate IDs match.
6. build_portrait_generation_jobs() joins profile + appearance + output path.
7. select_portrait_generation_jobs() chooses one, N or all planned jobs.
8. --dry-run prints prompts and stops without a provider call.
9. Existing valid files are inspected and skipped unless --overwrite is used.
10. create provider only if at least one job still needs generation.
11. For each remaining job, call generate_portrait_with_retries().
12. Provider returns bytes; normalize_portrait_image() writes final WebP.
13. validate_portrait_collection() checks the complete planned state.
```

## File map in execution order

| Runtime position | File | Responsibility |
|---:|---|---|
| 1 | [`coverage.py`](coverage.py) | Loads the portrait plan and checks it against generated candidate IDs. |
| 2 | [`planning.py`](planning.py) | Creates and selects deterministic portrait jobs. |
| 3 | [`prompting.py`](prompting.py) | Builds one professional, text-free image prompt from the approved appearance contract. |
| 4 | [`client.py`](client.py) | Calls the configured OpenAI image model and returns image bytes. |
| 5 | [`generation.py`](generation.py) | Coordinates one provider call, retries and image normalisation. |
| 6 | [`images.py`](images.py) | Decodes, crops, resizes, converts, writes and inspects WebP files. |
| 7 | [`validation.py`](validation.py) | Validates required portraits, photo-free candidates and image metadata. |
| Shared | [`models.py`](models.py) | Carries job, result, metadata and collection-validation objects between stages. |

## Important functions and classes

### `load_portrait_coverage_plan(path)`

Reads `candidate_portrait_plan.json` and returns a validated
`PortraitCoveragePlan` with deterministic candidate sets and appearance data.

### `validate_portrait_coverage_against_profiles(plan, profiles)`

Checks that the plan refers only to known candidates, covers the intended
collection and does not assign contradictory states.

### `build_portrait_generation_jobs(...)`

Joins each portrait candidate with:

- its saved profile;
- its approved `PortraitAppearance`;
- the prompt from `build_portrait_prompt()`;
- the exact `candidate_ID.webp` output path.

The candidate ID is the mapping key across profile JSON, portrait file, rendered
PDF and later API metadata.

### `build_portrait_prompt(profile, appearance)`

Creates a fictional professional headshot prompt. It explicitly rejects labels,
text, frames, borders and other artifacts that could make the image unsuitable
for a CV.

### `OpenAIPortraitGenerator.generate(prompt, candidate_id)`

Calls the image provider. The provider layer returns bytes only; it does not
decide the final file format or path.

### `generate_portrait_with_retries(job, provider, ...)`

The one-job coordinator:

```text
provider.generate()
-> normalize_portrait_image()
-> PortraitGenerationResult
```

Retryable provider errors and correctable image errors use the fixed retry
budget. The function never loops indefinitely.

### `normalize_portrait_image(...)`

Decodes provider output, applies orientation, centre-crops it to a square,
resizes it to the configured dimension, converts it to RGB and saves WebP at the
approved path.

### `inspect_portrait_image(path)`

Reads an existing image and returns checked metadata. The CLI uses it to decide
whether an existing file can be skipped safely.

### `validate_portrait_collection(...)`

Confirms that planned portrait files exist and intentionally photo-free
candidates do not accidentally acquire a portrait.

## Integrity versus file validity

A file may be valid WebP but still be the wrong candidate image. The full
integrity chain is:

```text
candidate ID in profile
= candidate ID in portrait plan
= candidate ID in filename
= candidate ID in render job
= candidate ID in rendered PDF metadata
```

When a portrait is repaired, the corresponding PDF must be rerendered. Because
the PDF bytes change, the affected document must also be reingested.

## Failure behavior

| Failure | Behavior |
|---|---|
| Profile/plan candidate mismatch | Stop before provider work. |
| Existing image is invalid | Regenerate it or fail according to command mode. |
| Retryable provider failure | Retry within configured limit. |
| Invalid image bytes or dimensions | Retry within configured limit. |
| Final normalisation failure | Return `PortraitGenerationFailed`. |
| Missing planned portrait at rendering time | `--enforce-portrait-plan` stops rendering. |

## Connection to the next section

```text
candidate_profiles.json + candidate_ID.webp files
-> cv_rendering.build_cv_render_jobs()
-> Jinja HTML and WeasyPrint PDF
```

Photo-free candidates continue through rendering with initials instead of an
image.

## Commands

```powershell
docker compose -p ai-cv-screener-openai exec backend `
  python -m app.scripts.generate_candidate_portraits --help

docker compose -p ai-cv-screener-openai exec backend `
  python -m app.scripts.validate_candidate_portraits --help
```

## Related tests

- `test_candidate_portrait_plan.py`
- `test_portrait_generation_planning.py`
- `test_portrait_generation_images.py`
- `test_openai_portrait_generator.py`
- `test_portrait_generation_service.py`
- `test_generate_candidate_portraits_cli.py`
- `test_validate_candidate_portraits_cli.py`
