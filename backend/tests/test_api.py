from fastapi.testclient import TestClient

from backend.main import app, create_app

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
    assert response.json() == {"success": True, "output": "Hello World"}


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


def test_html_is_rejected_by_backend() -> None:
    response = client.post(
        "/api/run",
        json={"language": "html", "code": "<h1>Preview me</h1>"},
    )

    assert response.status_code == 422


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
