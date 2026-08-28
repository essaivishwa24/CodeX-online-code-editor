"""Code execution API routes."""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..models.code_request import (
    CodeRunRequest,
    CodeRunResponse,
    RuntimeStatusResponse,
    SQLResetRequest,
    SQLResetResponse,
)
from ..services.execution_service import ExecutionService, RuntimeUnavailableError

router = APIRouter(tags=["execution"])
execution_service = ExecutionService()
logger = logging.getLogger("uvicorn.error")


def log_runtime_diagnostics() -> None:
    diagnostics = execution_service.runtime_diagnostics()
    logger.info(
        "Runtime detection: Python: %s | Java: %s | Javac: %s | GCC: %s",
        *("available" if diagnostics[name] else "unavailable"
          for name in ("python", "java", "javac", "gcc")),
    )


@router.post(
    "/run",
    response_model=CodeRunResponse,
    response_model_exclude_none=True,
    responses={
        503: {
            "model": CodeRunResponse,
            "description": "The selected language runtime is not installed.",
        }
    },
)
async def run_code(request: CodeRunRequest) -> CodeRunResponse | JSONResponse:
    """Run validated code using the development-only execution service."""

    try:
        result = await execution_service.execute(
            request.language,
            request.code,
            request.stdin,
            request.workspace_id,
        )
    except RuntimeUnavailableError as exc:
        response = CodeRunResponse(
            success=False,
            status="unavailable",
            stderr=str(exc),
            execution_time=0,
            error=str(exc),
        )
        return JSONResponse(
            status_code=503,
            content=response.model_dump(exclude_none=True),
        )

    return CodeRunResponse(
        success=result.success,
        status=result.status,
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
        execution_time=result.execution_time,
        memory_usage=result.memory_usage,
        columns=result.columns,
        rows=result.rows,
        row_count=result.row_count,
        message=result.message,
        output=result.output,
        error=result.error,
    )


@router.post("/sql/reset", response_model=SQLResetResponse)
async def reset_sql_playground(request: SQLResetRequest) -> SQLResetResponse:
    """Clear only the isolated SQLite database for one editor workspace."""

    removed = await execution_service.reset_sql(request.workspace_id)
    message = (
        "SQL playground reset. Your next query will use a fresh database."
        if removed
        else "SQL playground is already empty."
    )
    return SQLResetResponse(success=True, message=message)


@router.get("/runtime-status", response_model=RuntimeStatusResponse)
def runtime_status() -> RuntimeStatusResponse:
    """Report whether each configured local runtime can currently be located."""

    return RuntimeStatusResponse(runtimes=execution_service.runtime_status())
