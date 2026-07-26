# Controlled dataset files

## Summary explanation

This folder contains committed JSON plans that make the synthetic corpus and
its retrieval diagnostics reproducible. These files describe what should be
generated or tested; they are not used as answer evidence.

## Files

| File | Purpose |
|---|---|
| [`candidate_dataset_plan.json`](candidate_dataset_plan.json) | Defines the 30 candidate slots, required profile facts, distributions, and controlled search scenarios. |
| [`candidate_portrait_plan.json`](candidate_portrait_plan.json) | Defines which candidates receive portraits and the approved appearance attributes used to generate them. |
| [`cv_query_robustness_matrix.json`](cv_query_robustness_matrix.json) | Defines paraphrase families and expected candidate-set behavior for provider-free retrieval evaluation. |

## Source-of-truth boundary

These plans control dataset creation and testing. Recruiter answers do not read
candidate facts from these JSON files. User-visible evidence comes from the
rendered PDF CVs after extraction, chunking, embedding, and retrieval.

## Related code

- `candidate_generation/models.py` validates the dataset plan.
- `portrait_generation/coverage.py` validates the portrait plan.
- `cv_retrieval/robustness_evaluation.py` validates and runs the query matrix.
- `core/config.py` defines the configurable paths to all three files.

## Changing a plan

A candidate-plan change normally requires regenerating profiles, portraits when
relevant, PDF CVs, and the Chroma index. A query-matrix change only affects the
retrieval diagnostic unless the application logic is also changed.
