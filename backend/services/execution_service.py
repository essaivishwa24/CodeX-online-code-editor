"""Development-only subprocess code execution.

This module reduces accidental exposure with strict request limits, fixed command
arguments, temporary working directories, a sanitized environment, timeouts, and
bounded output. It is not a production sandbox: subprocesses still run as the API
server's operating-system user. Production deployments must replace this service
with an isolated container or remote sandbox running under a locked-down identity.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from queue import Empty, Full, Queue
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from typing import Final

from ..models.code_request import SupportedLanguage

DEFAULT_TIMEOUT_SECONDS: Final[float] = 3.0
DEFAULT_OUTPUT_LIMIT_BYTES: Final[int] = 64 * 1024
DEFAULT_MAX_CONCURRENT_RUNS: Final[int] = 2
READ_CHUNK_BYTES: Final[int] = 4096


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Result produced by an execution attempt."""

    success: bool
    output: str | None = None
    error: str | None = None


class RuntimeUnavailableError(RuntimeError):
    """Raised when a requested language runtime cannot be located."""


class _OutputLimitExceeded(Exception):
    """Internal signal used to stop a noisy subprocess."""


class _ExecutionTimedOut(Exception):
    """Internal signal used when a subprocess exceeds its deadline."""


class ExecutionService:
    """Execute small snippets in a constrained, development-only subprocess."""

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        output_limit_bytes: int = DEFAULT_OUTPUT_LIMIT_BYTES,
        max_concurrent_runs: int = DEFAULT_MAX_CONCURRENT_RUNS,
        temp_root: Path | None = None,
        node_executable: str | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if output_limit_bytes <= 0:
            raise ValueError("output_limit_bytes must be positive")
        if max_concurrent_runs <= 0:
            raise ValueError("max_concurrent_runs must be positive")

        self.timeout_seconds = timeout_seconds
        self.output_limit_bytes = output_limit_bytes
        self.temp_root = temp_root
        self._node_executable = node_executable
        self._execution_slots = asyncio.Semaphore(max_concurrent_runs)

    async def execute(
        self,
        language: SupportedLanguage,
        code: str,
    ) -> ExecutionResult:
        """Execute code and translate process outcomes into an API-safe result."""

        async with self._execution_slots:
            return await self._execute_in_temporary_directory(language, code)

    async def _execute_in_temporary_directory(
        self,
        language: SupportedLanguage,
        code: str,
    ) -> ExecutionResult:
        temp_parent = str(self.temp_root) if self.temp_root is not None else None
        with tempfile.TemporaryDirectory(prefix="codex-run-", dir=temp_parent) as raw_dir:
            work_dir = Path(raw_dir).resolve()
            file_name = "main.py" if language is SupportedLanguage.PYTHON else "main.js"
            source_file = work_dir / file_name
            source_file.write_text(code, encoding="utf-8", newline="\n")
            try:
                source_file.chmod(0o600)
            except OSError:
                # Some Windows filesystems do not implement POSIX-style modes.
                pass

            command = self._build_command(language, source_file)
            environment = self._build_sanitized_environment(work_dir)
            try:
                if self._requires_threaded_subprocess():
                    return_code, raw_output = await self._run_process_in_thread(
                        command,
                        work_dir,
                        environment,
                    )
                else:
                    return_code, raw_output = await self._run_process_asynchronously(
                        command,
                        work_dir,
                        environment,
                    )
            except (FileNotFoundError, PermissionError) as exc:
                runtime_name = (
                    "Python"
                    if language is SupportedLanguage.PYTHON
                    else "JavaScript"
                )
                raise RuntimeUnavailableError(
                    f"The {runtime_name} runtime is unavailable on this server."
                ) from exc
            except _ExecutionTimedOut:
                return ExecutionResult(
                    success=False,
                    error=(
                        "Execution timed out after "
                        f"{self.timeout_seconds:g} seconds."
                    ),
                )
            except _OutputLimitExceeded:
                limit_kib = self.output_limit_bytes / 1024
                return ExecutionResult(
                    success=False,
                    error=f"Output exceeded the {limit_kib:g} KiB limit.",
                )

            output = self._decode_and_clean_output(raw_output, work_dir)
            if return_code == 0:
                return ExecutionResult(success=True, output=output)
            return ExecutionResult(
                success=False,
                error=output or f"Process exited with status {return_code}.",
            )

    def _build_command(
        self,
        language: SupportedLanguage,
        source_file: Path,
    ) -> list[str]:
        if language is SupportedLanguage.PYTHON:
            # -I ignores PYTHON* variables and user-site configuration; -S avoids
            # importing third-party site packages; -B prevents bytecode files.
            return [
                sys.executable,
                "-I",
                "-S",
                "-B",
                "-X",
                "utf8",
                str(source_file),
            ]

        node_executable = self._node_executable or shutil.which("node")
        if not node_executable:
            raise RuntimeUnavailableError(
                "The JavaScript runtime is unavailable on this server."
            )
        return [node_executable, "--no-addons", "--no-warnings", str(source_file)]

    @staticmethod
    def _build_sanitized_environment(work_dir: Path) -> dict[str, str]:
        """Build a minimal environment without inheriting application secrets."""

        work_dir_text = str(work_dir)
        environment = {
            "HOME": work_dir_text,
            "USERPROFILE": work_dir_text,
            "TMPDIR": work_dir_text,
            "TMP": work_dir_text,
            "TEMP": work_dir_text,
            "PATH": work_dir_text,
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "NO_COLOR": "1",
            "CODEX_RUNNER": "development-only",
        }

        if os.name == "nt":
            # Windows runtimes need the OS directory to locate core components.
            system_root = os.environ.get("SystemRoot", r"C:\Windows")
            environment["SystemRoot"] = system_root
            environment["WINDIR"] = system_root

        return environment

    @staticmethod
    def _requires_threaded_subprocess() -> bool:
        """Return whether asyncio subprocess transports are unsafe here.

        Uvicorn installs a SelectorEventLoop on Windows, whose subprocess APIs
        raise ``NotImplementedError``. A worker-thread runner avoids depending on
        the server's event-loop implementation while leaving the event loop free.
        """

        return os.name == "nt"

    async def _run_process_in_thread(
        self,
        command: list[str],
        work_dir: Path,
        environment: dict[str, str],
    ) -> tuple[int, bytes]:
        worker = asyncio.create_task(
            asyncio.to_thread(
                self._run_process_synchronously,
                command,
                work_dir,
                environment,
            )
        )
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError:
            # A Python thread cannot be cancelled. Wait for its bounded runner to
            # kill/reap the process before TemporaryDirectory removes its cwd.
            try:
                await asyncio.shield(worker)
            except Exception:
                pass
            raise

    async def _run_process_asynchronously(
        self,
        command: list[str],
        work_dir: Path,
        environment: dict[str, str],
    ) -> tuple[int, bytes]:
        process = await self._start_process(command, work_dir, environment)
        try:
            try:
                return await asyncio.wait_for(
                    self._read_bounded_output(process),
                    timeout=self.timeout_seconds,
                )
            except TimeoutError as exc:
                raise _ExecutionTimedOut from exc
        finally:
            if process.returncode is None:
                await self._terminate_process_tree(process)

    def _run_process_synchronously(
        self,
        command: list[str],
        work_dir: Path,
        environment: dict[str, str],
    ) -> tuple[int, bytes]:
        """Run with bounded streaming reads without asyncio subprocess support."""

        process_options: dict[str, object] = {}
        if os.name == "nt":
            process_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            process_options["start_new_session"] = True

        process = subprocess.Popen(
            command,
            cwd=str(work_dir),
            env=environment,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            **process_options,
        )
        if process.stdout is None:
            self._terminate_synchronous_process_tree(process)
            raise RuntimeError("Subprocess output pipe was not created.")

        chunks: Queue[bytes] = Queue(maxsize=4)
        reader_finished = threading.Event()
        stop_reader = threading.Event()
        reader_errors: list[BaseException] = []

        def read_output() -> None:
            try:
                while not stop_reader.is_set():
                    chunk = process.stdout.read(READ_CHUNK_BYTES)
                    if not chunk:
                        break
                    while not stop_reader.is_set():
                        try:
                            chunks.put(chunk, timeout=0.05)
                            break
                        except Full:
                            continue
            except BaseException as exc:  # pragma: no cover - defensive OS error
                reader_errors.append(exc)
            finally:
                reader_finished.set()

        reader = threading.Thread(
            target=read_output,
            name="codex-output-reader",
            daemon=True,
        )
        reader.start()

        output = bytearray()
        deadline = time.monotonic() + self.timeout_seconds
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise _ExecutionTimedOut

                try:
                    chunk = chunks.get(timeout=min(0.05, remaining))
                except Empty:
                    chunk = None

                if chunk is not None:
                    if len(output) + len(chunk) > self.output_limit_bytes:
                        raise _OutputLimitExceeded
                    output.extend(chunk)

                if reader_finished.is_set() and chunks.empty():
                    if reader_errors:
                        raise RuntimeError("Failed to read subprocess output.") from (
                            reader_errors[0]
                        )
                    return_code = process.poll()
                    if return_code is not None:
                        return return_code, bytes(output)
        except BaseException:
            if process.poll() is None:
                self._terminate_synchronous_process_tree(process)
            raise
        finally:
            stop_reader.set()
            reader.join(timeout=1.0)
            process.stdout.close()
            if process.poll() is None:
                self._terminate_synchronous_process_tree(process)

    @staticmethod
    def _terminate_synchronous_process_tree(process: subprocess.Popen[bytes]) -> None:
        """Best-effort bounded termination for the worker-thread runner."""

        if process.poll() is not None:
            return

        if os.name == "nt":
            system_root = os.environ.get("SystemRoot", r"C:\Windows")
            taskkill = Path(system_root) / "System32" / "taskkill.exe"
            if taskkill.exists():
                try:
                    killer = subprocess.Popen(
                        [
                            str(taskkill),
                            "/PID",
                            str(process.pid),
                            "/T",
                            "/F",
                        ],
                        shell=False,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except OSError:
                    killer = None
                if killer is not None:
                    try:
                        killer.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        killer.kill()
                        try:
                            killer.wait(timeout=1.0)
                        except subprocess.TimeoutExpired:
                            pass
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

        if process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass

        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            # Production isolation must enforce cleanup at the runtime boundary.
            pass

    @staticmethod
    async def _start_process(
        command: list[str],
        work_dir: Path,
        environment: dict[str, str],
    ) -> asyncio.subprocess.Process:
        process_options: dict[str, object] = {}
        if os.name == "nt":
            process_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            process_options["start_new_session"] = True

        return await asyncio.create_subprocess_exec(
            *command,
            cwd=str(work_dir),
            env=environment,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            **process_options,
        )

    async def _read_bounded_output(
        self,
        process: asyncio.subprocess.Process,
    ) -> tuple[int, bytes]:
        if process.stdout is None:
            raise RuntimeError("Subprocess output pipe was not created.")

        output = bytearray()
        while True:
            chunk = await process.stdout.read(READ_CHUNK_BYTES)
            if not chunk:
                break
            if len(output) + len(chunk) > self.output_limit_bytes:
                raise _OutputLimitExceeded
            output.extend(chunk)

        return_code = await process.wait()
        return return_code, bytes(output)

    @staticmethod
    async def _terminate_process_tree(process: asyncio.subprocess.Process) -> None:
        """Best-effort termination of the snippet and any child processes."""

        if process.returncode is not None:
            return

        if os.name == "nt":
            system_root = os.environ.get("SystemRoot", r"C:\Windows")
            taskkill = Path(system_root) / "System32" / "taskkill.exe"
            if taskkill.exists():
                killer = await asyncio.create_subprocess_exec(
                    str(taskkill),
                    "/PID",
                    str(process.pid),
                    "/T",
                    "/F",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                try:
                    await asyncio.wait_for(killer.wait(), timeout=1.0)
                except TimeoutError:
                    killer.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass

        try:
            await asyncio.wait_for(process.wait(), timeout=1.0)
        except TimeoutError:
            # Cleanup is best-effort; the production runner must enforce this at
            # the container/runtime boundary.
            pass

    @staticmethod
    def _decode_and_clean_output(raw_output: bytes, work_dir: Path) -> str:
        output = raw_output.decode("utf-8", errors="replace")
        work_dir_text = str(work_dir)
        output = output.replace(work_dir_text, "<sandbox>")
        output = output.replace(work_dir_text.replace("\\", "/"), "<sandbox>")
        return output.rstrip("\r\n")
