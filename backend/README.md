# CodeX backend

FastAPI backend for Python and JavaScript snippet execution. HTML/CSS is not sent
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
- Interactive documentation at `http://127.0.0.1:8010/docs`

The default CORS allowlist covers Vite development (`5173`) and preview (`4173`)
on `localhost` and `127.0.0.1`. For another frontend origin, set a comma-separated
allowlist before starting the API:

```powershell
$env:CODEX_CORS_ORIGINS = "https://editor.example.com,http://localhost:4400"
```

Run the test suite from the project root with `python -m pytest backend/tests`.

## Security boundary

`ExecutionService` is explicitly a **development-only** runner. It uses fixed
subprocess arguments (never a shell), isolated temporary working directories, a
sanitized environment, Python isolated mode, a three-second timeout, a 64 KiB
combined-output cap, limited concurrency, and process-tree cleanup.

These controls do not provide a complete sandbox. Code still runs as the backend
OS user and can potentially access files or the network allowed to that user;
language-runtime escapes and denial-of-service techniques may also exist. Do not
expose this runner to untrusted internet traffic. A production deployment must
replace it with an ephemeral container or remote execution service with a read-only
root filesystem, non-root user, syscall filtering, disabled networking, CPU/memory/
process quotas, and no mounted application data or credentials.
