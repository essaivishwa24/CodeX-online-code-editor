from fastapi.testclient import TestClient
import pytest

from backend.main import app, create_app
from backend.routes import code_runner
from backend.services.execution_service import ExecutionService

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_run_python_code() -> None:
    response = client.post(
        "/api/run",
        json={"language": "python", "code": "print('Hello World')"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "success"
    assert body["stdout"] == body["output"] == "Hello World"
    assert body["stderr"] == ""
    assert body["exit_code"] == 0
    assert body["execution_time"] >= 0


def test_run_javascript_code() -> None:
    response = client.post(
        "/api/run",
        json={"language": "javascript", "code": 'console.log("JavaScript works");'},
    )
    assert response.status_code == 200
    assert response.json()["stdout"] == "JavaScript works"


@pytest.mark.parametrize("alias", ["c++", "cplusplus"])
def test_cpp_language_aliases_are_normalized(monkeypatch, tmp_path, alias) -> None:
    monkeypatch.setattr(
        code_runner,
        "execution_service",
        ExecutionService(temp_root=tmp_path, cpp_compiler="missing/g++"),
    )
    response = client.post(
        "/api/run",
        json={"language": alias, "code": "int main() { return 0; }"},
    )

    assert response.status_code == 503
    assert "g++" in response.json()["stderr"]


def test_run_typescript_code() -> None:
    response = client.post(
        "/api/run",
        json={
            "language": "typescript",
            "code": 'const language: string = "TypeScript";\nconsole.log(language + " works");',
        },
    )
    assert response.status_code == 200
    assert response.json()["stdout"] == "TypeScript works"


def test_runtime_error_is_returned_without_crashing_api() -> None:
    response = client.post(
        "/api/run",
        json={"language": "python", "code": "print(1 / 0)"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert "ZeroDivisionError" in body["error"]
    assert "codex-run-" not in body["error"]


def test_sql_run_returns_columns_rows_and_count(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        code_runner,
        "execution_service",
        ExecutionService(sql_storage_root=tmp_path),
    )
    response = client.post(
        "/api/run",
        json={
            "language": "sql",
            "workspace_id": "api-workspace",
            "code": "CREATE TABLE items (id INTEGER, name TEXT); "
                    "INSERT INTO items VALUES (1, 'one'); "
                    "SELECT * FROM items;",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["columns"] == ["id", "name"]
    assert body["rows"] == [[1, "one"]]
    assert body["row_count"] == 1


def test_sql_reset_clears_only_the_playground(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        code_runner,
        "execution_service",
        ExecutionService(sql_storage_root=tmp_path),
    )
    client.post(
        "/api/run",
        json={
            "language": "sql",
            "workspace_id": "api-workspace",
            "code": "CREATE TABLE disposable (id INTEGER);",
        },
    )
    reset = client.post(
        "/api/sql/reset",
        json={"workspace_id": "api-workspace"},
    )
    query = client.post(
        "/api/run",
        json={
            "language": "sql",
            "workspace_id": "api-workspace",
            "code": "SELECT * FROM disposable;",
        },
    )

    assert reset.status_code == 200
    assert reset.json()["success"] is True
    assert query.json()["status"] == "sql_error"


def test_runtime_status_endpoint() -> None:
    response = client.get("/api/runtime-status")

    assert response.status_code == 200
    assert response.json()["runtimes"]["python"]["available"] is True
    assert response.json()["runtimes"]["sql"]["available"] is True


@pytest.mark.parametrize(("language", "code"), [("html", "<h1>Preview me</h1>"), ("css", "body {}")])
def test_browser_languages_are_rejected_by_backend(language: str, code: str) -> None:
    response = client.post(
        "/api/run",
        json={"language": language, "code": code},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("language", "service_kwargs", "tool"),
    [
        ("java", {"java_compiler": "missing/javac"}, "javac"),
        ("c", {"c_compiler": "missing/gcc"}, "gcc"),
        ("cpp", {"cpp_compiler": "missing/g++"}, "g++"),
    ],
)
def test_missing_compiler_api_response(monkeypatch, language, service_kwargs, tool) -> None:
    monkeypatch.setattr(code_runner, "execution_service", ExecutionService(**service_kwargs))
    response = client.post("/api/run", json={"language": language, "code": "placeholder"})

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert tool in response.json()["stderr"]


def test_blank_code_is_rejected() -> None:
    response = client.post(
        "/api/run",
        json={"language": "python", "code": "  \n\t"},
    )

    assert response.status_code == 422
    assert "Code must not be empty" in response.text


def test_unknown_request_fields_are_rejected() -> None:
    response = client.post(
        "/api/run",
        json={"language": "python", "code": "print(1)", "admin": True},
    )

    assert response.status_code == 422


def test_cors_allows_local_vite_frontend() -> None:
    response = client.options(
        "/api/run",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_origins_can_be_configured(monkeypatch) -> None:
    monkeypatch.setenv(
        "CODEX_CORS_ORIGINS",
        "https://editor.example.com, http://localhost:4400/",
    )
    configured_client = TestClient(create_app())

    response = configured_client.options(
        "/api/run",
        headers={
            "Origin": "https://editor.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://editor.example.com"
