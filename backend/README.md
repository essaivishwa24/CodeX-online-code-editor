# CodeX backend

FastAPI backend for Python, JavaScript, TypeScript, Java, C, C++, and isolated SQLite SQL execution. HTML/CSS is not sent
to this API; the frontend renders it in a sandboxed iframe.

## Run locally

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements-dev.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8010
```

The API exposes:

- `GET /api/health`
- `POST /api/run` with JSON such as
  `{"language":"python","code":"print('Hello from CodeX!')"}`
- `POST /api/sql/reset` with `{"workspace_id":"..."}`
- `GET /api/runtime-status`
- Interactive documentation at `http://127.0.0.1:8010/docs`

The default CORS allowlist covers Vite development (`5173`) and preview (`4173`)
on `localhost` and `127.0.0.1`. For another frontend origin, set a comma-separated
allowlist before starting the API:

```powershell
$env:CODEX_CORS_ORIGINS = "https://editor.example.com,http://localhost:4400"
```

Run the test suite from the project root with `python -m pytest backend/tests`.

Java requires a JDK that exposes both `javac` and `java` on `PATH`. C requires
GCC's `gcc`; C++ requires `g++`. Missing tools return HTTP 503 with an actionable
message. SQL uses Python's built-in `sqlite3` module and needs no extra package.

Java is resolved dynamically for every run in this order: `JAVA_EXECUTABLE` or
`JAVAC_EXECUTABLE`, `JAVA_HOME/bin`, then `PATH`. GCC is resolved from
`GCC_EXECUTABLE`, `PATH`, then validated common MSYS2/MinGW locations on Windows.
Configure optional overrides in `.env`; see `.env.example`. Runtime status is not
permanently cached, and startup logs report Python, Java, Javac, and GCC
availability without exposing executable paths through the API.

SQL playground databases are stored below `backend/data/sql_playgrounds/` using
hashed workspace IDs. This location and connection are separate from `codex.db`,
which stores users and projects. Reset removes only the selected playground.

## Security boundary

`ExecutionService` is explicitly a **development-only** runner. It uses fixed
subprocess arguments (never a shell), isolated temporary working directories, a
sanitized environment, Python isolated mode, a five-second timeout, a 64 KiB
combined-output cap, limited concurrency, and process-tree cleanup.

These controls do not provide a complete sandbox. Code still runs as the backend
OS user and can potentially access files or the network allowed to that user;
language-runtime escapes and denial-of-service techniques may also exist. Do not
expose this runner to untrusted internet traffic. A production deployment must
replace it with an ephemeral container or remote execution service with a read-only
root filesystem, non-root user, syscall filtering, disabled networking, CPU/memory/
process quotas, and no mounted application data or credentials.
