# CodeX — Online Code Editor

CodeX is a portfolio-ready, full-stack online code editor built with React, Vite, Tailwind CSS, Monaco Editor, and FastAPI. It runs Python, JavaScript, TypeScript, Java, C, C++, and isolated SQLite SQL through a deliberately isolated **development-only** local runner and renders HTML/CSS/JavaScript projects in a sandboxed browser preview.

## Features

- Monaco-powered editing with syntax highlighting, autocomplete, indentation, bracket matching, and dark/light themes
- Python, JavaScript, TypeScript, Java, C, C++, and SQL execution through `POST /api/run`
- Structured SQL result tables and a confirmed reset action for each project's isolated playground database
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
- A JDK with both `javac` and `java` on `PATH` to execute Java
- GCC with `gcc` on `PATH` to execute C (`g++` is also required for C++)

Check the optional compiled-language runtimes before starting the backend:

```powershell
gcc --version
javac -version
java -version
```

On Windows, install a JDK (not only a JRE) and a GCC distribution such as
MSYS2/MinGW-w64, then restart the terminal after adding their `bin` directories
to `PATH`. `GET /api/runtime-status` reports what the backend can currently find.
The backend also resolves Java from `JAVA_HOME/bin` and checks common MSYS2/MinGW
GCC locations. Optional `JAVA_EXECUTABLE`, `JAVAC_EXECUTABLE`, and
`GCC_EXECUTABLE` values in `backend/.env` take precedence, so no personal paths
need to be committed.

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

Execution responses contain separate stdout/stderr, status, exit code, elapsed time, and nullable memory usage. API execution languages are `python`, `javascript`, `typescript`, `java`, `c`, `cpp`, and `sql`; HTML/CSS is previewed only in the client. SQL responses additionally contain `columns`, `rows`, `row_count`, and `message`. Node.js and project-local TypeScript are installed for JavaScript/TypeScript. Java needs `javac`/`java`, C needs `gcc`, and C++ needs `g++` available in PATH.

SQL playground files are stored under `backend/data/sql_playgrounds/`, keyed by a
hashed editor workspace ID. They are separate from the SQLAlchemy application
database. `ATTACH`, `DETACH`, `PRAGMA`, extension loading, transaction control,
triggers, and virtual tables are blocked. `POST /api/sql/reset` deletes only the
selected playground.

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

## Full-stack persistence upgrade

The branch includes SQLAlchemy relational persistence backed by SQLite by default (set `DATABASE_URL` for PostgreSQL), JWT authentication, protected project/file CRUD, version checkpoints, favorites, public share tokens, ZIP download, filename validation, stdin-aware execution, and an authenticated dashboard/editor flow. Models live in `backend/db_models.py`; startup creates missing tables and `backend/migrations/0001_initial.sql` is the baseline schema.

Implemented endpoints include `/api/auth/register`, `/api/auth/login`, `/api/auth/me`, `/api/auth/logout`, `/api/projects`, `/api/projects/{id}`, `/api/projects/{id}/files`, `/api/projects/{id}/download`, `/api/share/{token}`, `/api/run`, `/api/sql/reset`, `/api/runtime-status`, and `/api/admin/stats`.

Remaining limitations: AI provider integration, complete admin screens, Monaco diagnostics/formatting, rate limiting, Docker enforcement, and a formal Alembic revision chain. The local runner remains explicitly development-only.
