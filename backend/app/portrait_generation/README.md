# Portrait generation

## Summary explanation

This section creates fictional candidate portraits from a committed coverage
plan. It keeps candidate-to-image mapping deterministic, builds text-free image
prompts, normalises provider output into consistent WebP files, and validates
that the final portrait collection matches the plan.

```text
CandidateProfile + portrait plan
-> deterministic job
-> image prompt
-> OpenAI image generation
-> image normalisation
-> candidate_ID.webp
-> collection validation
```

## Files

| File | Purpose |
|---|---|
| [`models.py`](models.py) | Immutable portrait job, metadata, result, and collection-validation models. |
| [`coverage.py`](coverage.py) | Loads the committed portrait plan and checks it against candidate profiles. |
| [`planning.py`](planning.py) | Creates deterministic generation jobs and selects requested candidates. |
| [`prompting.py`](prompting.py) | Builds clean professional portrait prompts with no labels, frames, or text. |
| [`client.py`](client.py) | Calls the OpenAI image provider for fictional portraits. |
| [`images.py`](images.py) | Decodes, crops, resizes, converts, and inspects portrait image bytes. |
| [`generation.py`](generation.py) | Runs one portrait job with bounded retries and safe file replacement. |
| [`validation.py`](validation.py) | Proves that required portraits exist and photo-free candidates remain photo-free. |

## Integrity rule

A technically valid image is not enough. The filename, candidate ID, coverage
plan, and rendered CV must all agree. Portrait repairs therefore include
regenerating the approved file, rerendering the affected PDF, and rebuilding the
index when the PDF bytes change.

## Main commands

```powershell
docker compose exec backend python -m app.scripts.generate_candidate_portraits --help
docker compose exec backend python -m app.scripts.validate_candidate_portraits --help
```
