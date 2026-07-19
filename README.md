# AI CV Screener

## Quick local setup

1. Install Docker Desktop.
2. Clone this repository and open PowerShell in the project directory.
3. Run the interactive configuration assistant:

   ```powershell
   .\setup.ps1
   ```

4. Choose Gemini, OpenAI, or deterministic no-key mode.
5. Start the application:

   ```powershell
   docker compose up --build
   ```

The React application URL and API health URL are documented with the final UI
package. No Python file needs to be edited.

## Answer-provider modes

- **Gemini:** Uses `GEMINI_API_KEY` and the configured Gemini Flash model.
- **OpenAI:** Uses `OPENAI_API_KEY` and the configured OpenAI model.
- **Deterministic:** Requires no API key. It returns concise source-grounded
  answers directly from the validated retrieval result.
- **Auto:** Prefers Gemini when a Google key exists, then OpenAI, then the
  deterministic fallback.

Secrets are stored only in the local `.env` file. That file is ignored by Git.
The committed `.env.example` contains placeholders and safe defaults.

The synthetic CV-generation utilities still require OpenAI when a developer
chooses to regenerate the dataset. Normal question answering over the committed
CV collection does not require dataset regeneration.

## WP8 application API

FastAPI is available at `http://localhost:8000`. Interactive OpenAPI
documentation is available at `http://localhost:8000/docs`.

The frozen Patch 1 contract is:

```text
GET  /api/health
GET  /api/candidates
POST /api/chat
GET  /api/candidates/{candidate_id}/cv
```

A deterministic no-key request can be reviewed from PowerShell after Docker
Compose is running:

```powershell
$body = @{
    question = "Which candidates have experience with Python, FastAPI, and PostgreSQL?"
    candidate_limit = 5
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri http://localhost:8000/api/chat `
    -ContentType "application/json" `
    -Body $body | ConvertTo-Json -Depth 8
```

Unsupported questions are successful grounded responses with
`outcome: "unsupported"`; they are not server errors. Provider keys remain
server-side and are never accepted from or returned to the browser.
