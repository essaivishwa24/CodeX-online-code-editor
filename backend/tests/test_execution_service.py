import asyncio
import os
from pathlib import Path
import shutil

import pytest

from backend.models.code_request import SupportedLanguage
from backend.services.execution_service import (
    ExecutionService,
    RuntimeUnavailableError,
)


@pytest.mark.asyncio
async def test_threaded_runner_does_not_require_asyncio_subprocess_support(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unsupported_async_subprocess(*args: object, **kwargs: object) -> None:
        raise NotImplementedError("selector event loops cannot run subprocesses")

    monkeypatch.setattr(
        ExecutionService,
        "_requires_threaded_subprocess",
        staticmethod(lambda: True),
    )
    monkeypatch.setattr(
        asyncio,
        "create_subprocess_exec",
        unsupported_async_subprocess,
    )
    service = ExecutionService()

    result = await service.execute(
        SupportedLanguage.PYTHON,
        "print('threaded runner works')",
    )

    assert result.success is True
    assert result.output == "threaded runner works"


@pytest.mark.asyncio
async def test_timeout_stops_execution() -> None:
    service = ExecutionService(timeout_seconds=0.15)

    result = await service.execute(
        SupportedLanguage.PYTHON,
        "while True:\n    pass",
    )

    assert result.success is False
    assert result.error == "Execution timed out after 0.15 seconds."


@pytest.mark.asyncio
async def test_output_limit_stops_noisy_process() -> None:
    service = ExecutionService(output_limit_bytes=128)

    result = await service.execute(
        SupportedLanguage.PYTHON,
        "print('x' * 1000)",
    )

    assert result.success is False
    assert result.error == "Output exceeded the 0.125 KiB limit."


@pytest.mark.asyncio
async def test_backend_environment_is_not_inherited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEX_TEST_SECRET", "must-not-leak")
    service = ExecutionService()

    result = await service.execute(
        SupportedLanguage.PYTHON,
        "import os\nprint(os.environ.get('CODEX_TEST_SECRET', 'missing'))",
    )

    assert result.success is True
    assert result.output == "missing"


@pytest.mark.asyncio
async def test_temporary_directory_is_cleaned(tmp_path: Path) -> None:
    service = ExecutionService(temp_root=tmp_path)

    result = await service.execute(SupportedLanguage.PYTHON, "print('done')")

    assert result.success is True
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_javascript_execution_when_node_is_available() -> None:
    if shutil.which("node") is None:
        pytest.skip("Node.js is not installed")
    service = ExecutionService()

    result = await service.execute(
        SupportedLanguage.JAVASCRIPT,
        "console.log('Hello from JavaScript');",
    )

    assert result.success is True
    assert result.output == "Hello from JavaScript"


@pytest.mark.asyncio
async def test_missing_node_runtime_is_reported() -> None:
    missing_runtime = os.path.join("missing", "node")
    service = ExecutionService(node_executable=missing_runtime)

    with pytest.raises(RuntimeUnavailableError, match="JavaScript runtime"):
        await service.execute(
            SupportedLanguage.JAVASCRIPT,
            "console.log('hello')",
        )
