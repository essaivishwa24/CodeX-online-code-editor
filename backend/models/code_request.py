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


class CodeRunRequest(BaseModel):
    """A validated code execution request."""

    model_config = ConfigDict(extra="forbid")

    language: SupportedLanguage
    code: str = Field(strict=True, min_length=1, max_length=MAX_CODE_LENGTH)

    @field_validator("language", mode="before")
    @classmethod
    def normalize_language(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("code")
    @classmethod
    def reject_blank_code(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Code must not be empty.")
        return value


class CodeRunResponse(BaseModel):
    """The stable response shape returned by the execution endpoint."""

    success: bool
    output: str | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Health-check response."""

    status: str

