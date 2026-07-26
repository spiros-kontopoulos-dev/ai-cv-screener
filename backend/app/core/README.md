# Core configuration and logging

## Summary explanation

This section is the foundation used by every other backend section. It does not
perform business work itself. It creates one validated configuration object and
one shared logging setup so the rest of the application does not read
environment variables or configure logs independently.

## Position in the architecture

```text
.env / Docker environment / built-in defaults
-> Settings()
-> cached get_settings()
-> generation, rendering, ingestion, retrieval, answer and API builders
```

Before this section runs, configuration exists only as environment-variable
text. After it runs, the application has typed Python values such as `Path`,
`int`, `float`, `bool`, provider mode and secret fields.

## Runtime order

### Server startup

```text
uvicorn imports app.main
-> main.py calls get_settings()
-> get_settings() creates Settings() once
-> Pydantic reads environment variables and validates all values
-> main.py creates FastAPI with those settings
-> lifespan() calls configure_logging(settings.log_level)
```

### Script startup

```text
script run_cli()
-> settings argument supplied by a test, or get_settings()
-> command reads paths, limits and provider settings
-> command builds the relevant service
```

The `@lru_cache` on `get_settings()` means one process normally uses one
`Settings` instance. Tests can still construct `Settings(...)` directly when
they need isolated values.

## Files and runtime role

| File | Runtime role |
|---|---|
| [`config.py`](config.py) | Converts defaults and environment variables into the shared typed `Settings` object. |
| [`logging.py`](logging.py) | Applies the requested log level and one consistent backend log format. |
| [`__init__.py`](__init__.py) | Keeps the package import boundary small. |

## Important objects and functions

### `Settings`

`Settings` is the central Pydantic settings model. Its fields follow the main
application flow:

1. application name, environment, CORS origin and provider keys;
2. committed dataset and portrait-plan paths;
3. generated profile, image and PDF locations;
4. chunking settings;
5. embedding model and vector dimension;
6. Chroma path, collection name and compatibility version;
7. raw, assisted, candidate and final retrieval limits;
8. answer-provider selection and generation limits;
9. portrait and candidate-generation provider settings.

Important behavior:

- environment names are case-insensitive;
- unknown environment values are ignored so one `.env` can serve several tools;
- `SecretStr` prevents API keys from appearing in normal string output;
- `Field(...)` constraints reject invalid values such as negative limits;
- committed JSON paths are resolved from the package location so they do not depend on the current working directory.

### `get_settings()`

```python
get_settings() -> Settings
```

Creates and caches the shared configuration. API dependencies, scripts and
service builders call this function rather than creating unrelated settings
objects.

### `configure_logging(level)`

Normalises the configured log level and calls `logging.basicConfig(...)`. It is
called by the FastAPI lifespan before requests are accepted.

## Which settings affect persisted data

Some changes are safe at the next process restart. Others require rebuilding the
vector index.

### Usually no index rebuild

- CORS origin;
- provider mode or hosted model;
- answer length and retry limits;
- API log level;
- frontend-facing application labels.

### Rebuild the index

- embedding model name;
- expected embedding dimension;
- vector distance metric;
- chunking version or chunk size rules;
- vector index version;
- Chroma collection identity.

These values are stored as collection metadata. `CvChromaRepository` rejects an
incompatible collection rather than mixing records produced with different
rules.

## Connections to other sections

```text
core.Settings
├── candidate_generation scripts and OpenAI client
├── portrait_generation scripts and image client
├── cv_rendering path planning
├── cv_ingestion service construction
├── cv_retrieval builder chain
├── cv_answer_generation provider selection
├── services candidate catalogue
└── api health, dependencies and CORS
```

## Configuration boundary

Only backend code receives provider keys. The React frontend uses
`VITE_API_BASE_URL`, which is public browser configuration. Never put a provider
secret in a Vite variable.

## Related tests

Configuration behavior is exercised indirectly across the suite, especially:

- API health and CORS tests;
- provider-selection tests;
- ingestion and vector-store compatibility tests;
- local setup-script tests.
