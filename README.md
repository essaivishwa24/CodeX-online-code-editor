# CodeX — Online Code Editor

CodeX is a portfolio-ready, full-stack online code editor built with React, Vite, Tailwind CSS, Monaco Editor, and FastAPI. It runs Python and JavaScript through a deliberately isolated **development-only** local runner and renders HTML/CSS in a sandboxed browser preview.

## Features

- Monaco-powered editing with syntax highlighting, autocomplete, indentation, bracket matching, and dark/light themes
- Python and JavaScript execution through `POST /api/run`
- Sandboxed HTML/CSS preview that never sends markup to the execution API
- Terminal-style output with running, success, error, and timeout states
- Keyboard execution with <kbd>Ctrl</kbd>/<kbd>Cmd</kbd> + <kbd>Enter</kbd>
- Per-language drafts and preferences persisted in `localStorage`
- Copy code/output, download, clear, starter-code reset, and editor fullscreen actions
- Responsive, resizable editor/output workspace
- Live language, line, character, and execution-status details
- Request validation, execution timeout, bounded output, temporary working directories, and a minimal child-process environment

## Project structure

```text
Code-editor-project/
├── backend/                 # FastAPI API and development runner
├── frontend/                # React/Vite client
├── .gitignore
└── README.md
```

## Prerequisites

- Python 3.10 or newer
- Node.js 20.19+ or 22.12+ (also used to execute JavaScript snippets)
- npm

## Run the backend

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements-dev.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8010
```

The API is available at `http://127.0.0.1:8010`. Interactive documentation is available at `http://127.0.0.1:8010/docs`.

CodeX uses port `8010` consistently because port `8000` is already owned by a
different Windows process on this development machine. The backend, Vite proxy,
and documentation must remain on the same port.

## Run the frontend

In a second terminal, from the project root:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

To point the client at another backend, copy `frontend/.env.example` to `frontend/.env.local` and change `VITE_API_BASE_URL`.

For a frontend hosted on another origin, set the backend's comma-separated
`CODEX_CORS_ORIGINS` environment variable before starting Uvicorn.

## API

### `GET /api/health`

Returns the API readiness status.

### `POST /api/run`

Request:

```json
{
  "language": "python",
  "code": "print('Hello from CodeX!')"
}
```

Successful execution:

```json
{
  "success": true,
  "output": "Hello from CodeX!"
}
```

Program errors are returned in a normalized response with `success: false` and a readable `error` value. Supported API execution languages are `python` and `javascript`; HTML/CSS is previewed only in the client.

## Verification

```powershell
# Backend
python -m pytest backend/tests

# Frontend
cd frontend
npm test
npm run build
```

## Security limitation

The local execution service is intentionally labeled **development-only**. It improves safety with allowlisted runtimes, argument-list subprocesses (no shell), isolated interpreter mode for Python, temporary working directories, a minimal environment, input/output limits, timeouts, and process cleanup. These controls are not an operating-system sandbox: locally executed code may still access host resources permitted to the current user.

Never expose this runner to untrusted users or the public internet. A production deployment must replace it with a hardened sandbox such as an ephemeral container or microVM with disabled networking, a read-only/minimal filesystem, an unprivileged user, and CPU/memory/process limits.
