# AI CV Screener frontend

React 19, TypeScript, and Vite interface for the source-grounded CV assistant.
The browser consumes the frozen WP8 API contract and never receives provider
keys or other backend secrets.

## Local Docker use

From the repository root:

```powershell
docker compose up --build
```

Open:

- Application: `http://localhost:5173`
- FastAPI documentation: `http://localhost:8000/docs`
- API health: `http://localhost:8000/api/health`

`VITE_API_BASE_URL` defaults to `http://localhost:8000`. Vite variables are
compiled into or exposed to the browser, so they must contain public
configuration only.

## Frontend validation

From the repository root:

```powershell
docker compose run --rm frontend npm run lint
docker compose run --rm frontend npm run test
docker compose run --rm frontend npm run build
```

The tests cover API request/error behavior, candidate loading, supported,
partial and unsupported outcomes, provider diagnostics, citation evidence,
PDF page links, and recoverable failure states.

## Main source structure

```text
src/
├── api/                 # Frozen HTTP contracts and safe fetch client
├── components/          # Sidebar, chat, composer, badges and source drawer
├── hooks/               # Keyboard focus containment for overlays
├── App.tsx              # Application orchestration and request state
├── chatTypes.ts         # Conversation state contract
└── utils.ts             # Presentation-only formatting helpers
```
