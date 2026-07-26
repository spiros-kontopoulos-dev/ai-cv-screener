# Controlled dataset plans

## Summary explanation

This folder contains committed JSON plans that describe what the synthetic
corpus should contain and how retrieval should be tested. The plans make data
creation reproducible, but they are not used as recruiter-answer evidence.

## Position in the architecture

```text
Committed JSON plans
├── candidate generation plan
├── portrait coverage plan
└── query robustness matrix

Plans -> generation / validation / diagnostics
Rendered PDF CVs -> actual answer evidence
```

Before these files are read, the application knows only generic generation
rules. After they are validated, it knows the exact candidate slots, portrait
assignments and diagnostic query expectations.

## Files and consumers

| File | Main consumer | Output created from it |
|---|---|---|
| [`candidate_dataset_plan.json`](candidate_dataset_plan.json) | `candidate_generation.plan.load_candidate_dataset_plan()` | Candidate slots and final profile collection |
| [`candidate_portrait_plan.json`](candidate_portrait_plan.json) | `portrait_generation.coverage.load_portrait_coverage_plan()` | Portrait/photo-free job plan |
| [`cv_query_robustness_matrix.json`](cv_query_robustness_matrix.json) | `cv_retrieval.robustness_evaluation.load_query_robustness_matrix()` | Provider-free paraphrase evaluation report |

## Candidate dataset plan flow

```text
candidate_dataset_plan.json
-> CandidateDatasetPlan.model_validate()
-> validate plan count, IDs, distributions and scenario references
-> select_candidate_slots()
-> build_candidate_prompt(slot)
-> generate and validate CandidateProfile
-> save candidate_profiles.json
```

The plan contains controlled facts such as:

- candidate identity and role category;
- seniority and location;
- required skills, languages or education;
- locked numeric facts such as experience or team size;
- leadership, certification or project requirements;
- search scenarios used to validate the completed corpus.

## Portrait plan flow

```text
candidate_portrait_plan.json
-> PortraitCoveragePlan
-> compare candidate IDs with saved profiles
-> build portrait jobs only for planned candidates
-> leave the other candidates intentionally photo-free
```

This prevents the presence or absence of a portrait from being decided by
whatever files happen to exist in a directory.

## Query robustness matrix flow

```text
cv_query_robustness_matrix.json
-> load_query_robustness_matrix()
-> select question families
-> run FinalCvRetriever for every paraphrase
-> compare parser conditions and returned candidate sets
-> produce diagnostics without calling an answer provider
```

The matrix tests whether different recruiter phrasings preserve the intended
search meaning.

## Important source-of-truth boundary

These files are control inputs, not answer sources:

- candidate generation reads the plan;
- PDF rendering reads validated profile JSON;
- ingestion reads PDF bytes;
- retrieval reads indexed PDF chunks;
- answer generation cites those chunks.

A recruiter answer must never cite or silently use facts from the candidate
plan or profile JSON.

## What happens when a plan changes

### Candidate-plan change

Usually requires:

```text
regenerate affected profiles
-> validate collection
-> regenerate affected portraits when required
-> rerender affected PDFs
-> revalidate PDFs
-> reingest or rebuild the index
```

### Portrait-plan change

Usually requires portrait regeneration, PDF rerendering and PDF reingestion for
all changed candidates.

### Query-matrix change

Changes only the diagnostic input unless the new questions expose retrieval
logic that also needs code changes.

## Related settings and code

- `core/config.py` defines all three configurable paths.
- `candidate_generation/models.py` validates the candidate plan structure.
- `portrait_generation/coverage.py` validates portrait coverage.
- `cv_retrieval/robustness_evaluation.py` validates and runs the query matrix.
