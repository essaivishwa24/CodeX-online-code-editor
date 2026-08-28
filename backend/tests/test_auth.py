from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.auth import verify_password
from backend.database import Base, get_db
from backend.db_models import User
from backend.main import create_app


def make_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    application = create_app()

    def override_get_db():
        database = testing_session()
        try:
            yield database
        finally:
            database.close()

    application.dependency_overrides[get_db] = override_get_db
    return TestClient(application), testing_session


def register_user(client: TestClient):
    return client.post(
        "/api/auth/register",
        json={
            "username": "codextest",
            "email": "codextest@example.com",
            "password": "Test@12345",
        },
    )


def test_registration_login_me_refresh_and_password_hashing():
    client, testing_session = make_client()

    registration = register_user(client)
    assert registration.status_code == 200
    body = registration.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "codextest@example.com"
    assert "access_token" in body

    with testing_session() as database:
        user = database.scalar(select(User).where(User.email == "codextest@example.com"))
        assert user is not None
        assert user.password_hash != "Test@12345"
        assert verify_password("Test@12345", user.password_hash)

    login = client.post(
        "/api/auth/login",
        json={"email": "CODEXTEST@EXAMPLE.COM", "password": "Test@12345"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json() == {
        "id": body["user"]["id"],
        "username": "codextest",
        "email": "codextest@example.com",
        "role": "user",
    }

    # A page refresh reuses the same stored bearer token against /auth/me.
    refreshed_me = client.get("/api/auth/me", headers=headers)
    assert refreshed_me.status_code == 200
    assert refreshed_me.json() == me.json()
    assert client.get("/api/projects", headers=headers).status_code == 200
    assert client.post("/api/auth/logout", headers=headers).status_code == 200


def test_wrong_unknown_disabled_and_unauthorized_access():
    client, testing_session = make_client()
    register_user(client)

    wrong = client.post(
        "/api/auth/login",
        json={"email": "codextest@example.com", "password": "Wrong@12345"},
    )
    unknown = client.post(
        "/api/auth/login",
        json={"email": "missing@example.com", "password": "Wrong@12345"},
    )
    assert wrong.status_code == 401
    assert unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"] == "Invalid email or password"
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/projects").status_code == 401

    login = client.post(
        "/api/auth/login",
        json={"email": "codextest@example.com", "password": "Test@12345"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/admin/stats", headers=headers).status_code == 403

    with testing_session() as database:
        user = database.scalar(select(User).where(User.email == "codextest@example.com"))
        user.is_active = False
        database.commit()

    disabled = client.post(
        "/api/auth/login",
        json={"email": "codextest@example.com", "password": "Test@12345"},
    )
    assert disabled.status_code == 403
    assert disabled.json()["detail"] == "This account is currently disabled"
    assert client.get("/api/auth/me", headers=headers).status_code == 401
