# Candidate-aware CV retrieval

## Summary explanation

This section finds candidates from recruiter questions. It starts with broad
semantic recall, recovers exact lexical and numeric evidence, groups chunks by
candidate, checks requirement coverage, and builds a small final evidence
package for answer generation.

```text
Recruiter question
-> question analysis
-> broad semantic chunk recall
-> exact evidence recovery
-> candidate-level ranking
-> supported / partial / unsupported result
-> bounded final context
```

The key design rule is: **chunks are evidence units, but candidates are ranking
units**.

## Files

| File | Purpose |
|---|---|
| [`models.py`](models.py) | Contracts for the first raw semantic-search stage. |
| [`raw_retrieval.py`](raw_retrieval.py) | Embeds the question and retrieves a broad set of related Chroma chunks. |
| [`evidence_analysis.py`](evidence_analysis.py) | Normalises recruiter wording and extracts phrases, relations, education facts, and numeric constraints. |
| [`assisted_retrieval.py`](assisted_retrieval.py) | Combines semantic recall with a bounded exact-text recovery scan. |
| [`candidate_ranking.py`](candidate_ranking.py) | Converts query requirements and chunk evidence into ranked candidate results. |
| [`candidate_retrieval.py`](candidate_retrieval.py) | Coordinates assisted retrieval and candidate-level ranking. |
| [`final_retrieval.py`](final_retrieval.py) | Applies support thresholds and context budgets for answer generation. |
| [`evaluation.py`](evaluation.py) | Evaluates final retrieval against planned corpus scenarios. |
| [`robustness_evaluation.py`](robustness_evaluation.py) | Tests many ways a recruiter might ask the same question and reports parser and coverage details. |

## Why exact evidence follows semantic search

Semantic vectors are useful for recall, but similarity alone cannot prove every
requirement. For example, the number `8` may describe years of experience or a
team of eight engineers. `evidence_analysis.py` keeps the number connected to
its local relation before candidate coverage is awarded.

## Candidate support outcomes

- **Supported:** at least one candidate has strong evidence for every required
  condition.
- **Partial:** relevant candidates exist, but one or more conditions are not
  fully supported.
- **Unsupported:** the indexed CV evidence does not support the request.

## Main inspection commands

```powershell
docker compose exec backend python -m app.scripts.inspect_raw_cv_retrieval --help
docker compose exec backend python -m app.scripts.inspect_assisted_cv_retrieval --help
docker compose exec backend python -m app.scripts.inspect_candidate_cv_retrieval --help
docker compose exec backend python -m app.scripts.inspect_final_cv_retrieval --help
docker compose exec backend python -m app.scripts.evaluate_cv_query_robustness --help
```
