"""SQLAlchemy persistence for CodeX (SQLite by default, PostgreSQL-ready)."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(BACKEND_DIR / ".env", override=False)


def resolve_database_url(configured_url: str | None) -> str:
    """Resolve development SQLite paths independently of the launch directory."""

    if not configured_url:
        return f"sqlite:///{(PROJECT_ROOT / 'codex.db').as_posix()}"
    if configured_url.startswith("sqlite:///./"):
        relative_path = configured_url.removeprefix("sqlite:///./")
        return f"sqlite:///{(PROJECT_ROOT / relative_path).resolve().as_posix()}"
    return configured_url


DATABASE_URL = resolve_database_url(os.getenv("DATABASE_URL"))
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from . import db_models  # noqa: F401
    Base.metadata.create_all(bind=engine)
