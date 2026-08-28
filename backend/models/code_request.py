"""Validation models for the code execution API."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_CODE_LENGTH = 50_000


class SupportedLanguage(str, Enum):
    """Languages executed by the backend runner.

    HTML is intentionally absent: the frontend renders it in a sandboxed iframe.
    """

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    C = "c"
    CPP = "cpp"
    SQL = "sql"


class CodeRunRequest(BaseModel):
    """A validated code execution request."""

    model_config = ConfigDict(extra="forbid")

    language: SupportedLanguage
    code: str = Field(strict=True, min_length=1, max_length=MAX_CODE_LENGTH)
    stdin: str = Field(default="", max_length=10_000)
    workspace_id: str = Field(
        default="default",
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )

    @field_validator("language", mode="before")
    @classmethod
    def normalize_language(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            return {"c++": "cpp", "cplusplus": "cpp"}.get(normalized, normalized)
        return value

    @field_validator("code")
    @classmethod
    def reject_blank_code(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Code must not be empty.")
        return value

    @field_validator("workspace_id")
    @classmethod
    def normalize_workspace_id(cls, value: str) -> str:
        return value.strip()


class CodeRunResponse(BaseModel):
    """The stable response shape returned by the execution endpoint."""

    success: bool
    status: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    execution_time: float
    memory_usage: float | None = None
    columns: list[str] | None = None
    rows: list[list[object]] | None = None
    row_count: int | None = None
    message: str | None = None
    # Compatibility aliases for clients built against the original API.
    output: str | None = None
    error: str | None = None


class SQLResetRequest(BaseModel):
    """Identify one isolated SQL playground to clear."""

    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )


class SQLResetResponse(BaseModel):
    success: bool
    message: str


class RuntimeStatusEntry(BaseModel):
    available: bool
    detail: str


class RuntimeStatusResponse(BaseModel):
    runtimes: dict[str, RuntimeStatusEntry]


class HealthResponse(BaseModel):
    """Health-check response."""

    status: str
