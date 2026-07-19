# AI CV Screener

A local, source-grounded candidate search product built with FastAPI, React,
PyMuPDF, Sentence Transformers, ChromaDB, and direct hosted LLM providers with
a deterministic no-key fallback.

## Quick local setup

1. Install Docker Desktop.
2. Clone this repository and open PowerShell in the project directory.
3. Run the interactive configuration assistant:

   ```powershell
   .\setup.ps1
   ```

4. Choose Gemini, OpenAI, or deterministic no-key mode.
5. Start the complete product:

   ```powershell
   docker compose up --build
   ```

6. Open:

   - React application: `http://localhost:5173`
   - FastAPI documentation: `http://localhost:8000/docs`
   - API health: `http://localhost:8000/api/health`

No Python or TypeScript source file needs to be edited for local setup.

## Product flow

```text
Question
-> semantic recall
-> relation-aware exact evidence
-> candidate-level ranking
-> support classification
-> bounded context
-> grounded answer generation
-> validated candidate-owned citations
-> React evidence and CV-page presentation
```

The UI loads the real indexed candidate catalogue, sends grounded chat
requests, distinguishes supported, partial, and unsupported results, highlights
ranked candidates, and opens citation evidence down to the PDF file and page.

## Answer-provider modes

- **Gemini:** Uses `GEMINI_API_KEY` and the configured Gemini model.
- **OpenAI:** Uses `OPENAI_API_KEY` and the configured OpenAI model.
- **Deterministic:** Requires no API key and returns concise grounded answers
  directly from the validated retrieval result.
- **Auto:** Prefers Gemini when a Google key exists, then OpenAI, then the
  deterministic fallback.

Secrets are stored only in the local root `.env` file. That file is ignored by
Git. Provider keys are never exposed through the API or through `VITE_`
variables, because Vite variables are public browser configuration.

## Application API

```text
GET  /api/health
GET  /api/candidates
POST /api/chat
GET  /api/candidates/{candidate_id}/cv
```

The API returns safe validation/error envelopes and serves candidate PDFs only
through trusted indexed metadata.

## Validation

Backend:

```powershell
docker compose run --rm backend pytest -q
```

Frontend:

```powershell
docker compose run --rm frontend npm run lint
docker compose run --rm frontend npm run test
docker compose run --rm frontend npm run build
```

The synthetic CV-generation utilities still require OpenAI when a developer
chooses to regenerate the dataset. Normal question answering over the committed
CV collection does not require dataset regeneration.
