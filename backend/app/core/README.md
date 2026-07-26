# Core configuration

## Summary explanation

This section holds the small pieces shared by the whole backend: validated
settings and logging setup. Other modules use these helpers instead of reading
environment variables or configuring logging independently.

## Files

| File | Purpose |
|---|---|
| [`config.py`](config.py) | Defines the central Pydantic `Settings` model and cached `get_settings()` function. |
| [`logging.py`](logging.py) | Applies one log level and output format for the backend process. |

## Settings groups

`Settings` keeps the application configuration in the same order as the main
flow:

1. application name, environment, CORS origin, and provider keys;
2. candidate and portrait plan paths;
3. profile, image, and PDF locations;
4. chunking and embedding configuration;
5. ChromaDB collection compatibility settings;
6. raw, assisted, candidate, and final retrieval limits;
7. grounded-answer provider and model settings.

Environment variables use upper-case field names. For example,
`CV_EMBEDDING_BATCH_SIZE` overrides `cv_embedding_batch_size`.

## Important rules

- `SecretStr` prevents provider keys from being printed accidentally.
- `get_settings()` is cached, so the process reuses one validated object.
- The embedding model, dimension, chunking version, and index version must agree
  with the metadata stored in ChromaDB.
- Changing ingestion compatibility settings requires rebuilding the index.

Local values are configured through the root `.env` file created by `setup.ps1`
or `setup.sh`.
