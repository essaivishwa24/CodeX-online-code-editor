"""Code execution API routes."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..models.code_request import CodeRunRequest, CodeRunResponse
from ..services.execution_service import ExecutionService, RuntimeUnavailableError

router = APIRouter(tags=["execution"])
execution_service = ExecutionService()


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
        result = await execution_service.execute(request.language, request.code)
    except RuntimeUnavailableError as exc:
        response = CodeRunResponse(success=False, error=str(exc))
        return JSONResponse(
            status_code=503,
            content=response.model_dump(exclude_none=True),
        )

    if result.success:
        return CodeRunResponse(success=True, output=result.output)
    return CodeRunResponse(success=False, error=result.error)

