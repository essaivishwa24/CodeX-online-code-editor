"""Development-only, bounded subprocess runners for CodeX languages.

Each language has a small runner that declares its source file, compiler step,
and execution command. The process boundary is shared so timeout, output limit,
temporary-directory cleanup, environment filtering, and process-tree cleanup are
applied consistently. This is defense-in-depth for local development, not a
production sandbox; production must replace this service with isolated containers.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from queue import Empty, Full, Queue
import re
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
from .sql_execution_service import SQLExecutionResult, SQLExecutionService

DEFAULT_TIMEOUT_SECONDS: Final[float] = 5.0
DEFAULT_OUTPUT_LIMIT_BYTES: Final[int] = 64 * 1024
DEFAULT_MAX_CONCURRENT_RUNS: Final[int] = 2
READ_CHUNK_BYTES: Final[int] = 4096
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQL_STORAGE_ROOT = PROJECT_ROOT / "backend" / "data" / "sql_playgrounds"
WINDOWS_GCC_CANDIDATES: Final[tuple[Path, ...]] = (
    Path(r"C:\msys64\mingw64\bin\gcc.exe"),
    Path(r"C:\msys64\ucrt64\bin\gcc.exe"),
    Path(r"C:\mingw64\bin\gcc.exe"),
    Path(r"C:\MinGW\bin\gcc.exe"),
)
WINDOWS_GPP_CANDIDATES: Final[tuple[Path, ...]] = tuple(
    candidate.with_name("g++.exe") for candidate in WINDOWS_GCC_CANDIDATES
)


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    success: bool
    status: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    execution_time: float = 0.0
    memory_usage: float | None = None
    columns: list[str] | None = None
    rows: list[list[object]] | None = None
    row_count: int | None = None
    message: str | None = None

    @property
    def output(self) -> str | None:
        return self.stdout if self.success else None

    @property
    def error(self) -> str | None:
        return self.stderr if not self.success else None


@dataclass(frozen=True, slots=True)
class RunnerPlan:
    source_name: str
    run_command: list[str]
    compile_command: list[str] | None = None
    runtime_path_entries: tuple[str, ...] = ()


class RuntimeUnavailableError(RuntimeError):
    """Raised when a selected language's required tools cannot be located."""


class SourceValidationError(ValueError):
    """Raised when a source-file convention cannot be satisfied safely."""


class _OutputLimitExceeded(Exception):
    pass


class _ExecutionTimedOut(Exception):
    pass


def _resolve_tool_candidate(command: str | os.PathLike[str] | None) -> str | None:
    if command is None:
        return None
    configured = os.path.expandvars(str(command)).strip().strip('"')
    if not configured:
        return None
    candidate = Path(configured).expanduser()
    if candidate.is_file():
        return str(candidate.resolve())
    located = shutil.which(configured)
    return str(Path(located).resolve()) if located else None


def _require_tool(command: str | None, message: str) -> str:
    resolved = _resolve_tool_candidate(command)
    if not resolved:
        raise RuntimeUnavailableError(message)
    return resolved


def _tool_is_available(command: str | None) -> bool:
    return _resolve_tool_candidate(command) is not None


def _probe_tool(executable: str | None, version_argument: str) -> bool:
    """Check that a resolved executable starts and reports a successful version."""

    if not executable:
        return False
    options: dict[str, object] = {}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        completed = subprocess.run(
            [executable, version_argument],
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
            check=False,
            **options,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


class LanguageRunner:
    def validate_source(self, code: str) -> None:
        del code

    def plan(self, work_dir: Path) -> RunnerPlan:
        raise NotImplementedError


class PythonRunner(LanguageRunner):
    def plan(self, work_dir: Path) -> RunnerPlan:
        source = work_dir / "main.py"
        return RunnerPlan(
            source_name=source.name,
            run_command=[sys.executable, "-I", "-S", "-B", "-X", "utf8", str(source)],
        )


class JavaScriptRunner(LanguageRunner):
    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable

    def plan(self, work_dir: Path) -> RunnerPlan:
        node = _require_tool(
            self.executable or "node",
            "JavaScript runtime is unavailable. Execution requires Node.js to be installed and available in PATH.",
        )
        source = work_dir / "main.js"
        return RunnerPlan(source.name, [node, "--no-addons", "--no-warnings", str(source)])


class TypeScriptRunner(LanguageRunner):
    def __init__(self, node_executable: str | None = None, compiler: str | None = None) -> None:
        self.node_executable = node_executable
        self.compiler = compiler

    def plan(self, work_dir: Path) -> RunnerPlan:
        node = _require_tool(
            self.node_executable or "node",
            "TypeScript execution requires Node.js to be installed and available in PATH.",
        )
        source = work_dir / "main.ts"
        output = work_dir / "main.js"
        local_compiler = PROJECT_ROOT / "frontend" / "node_modules" / "typescript" / "bin" / "tsc"
        compiler = Path(self.compiler) if self.compiler else local_compiler
        if compiler.exists():
            compile_command = [
                node,
                str(compiler),
                "--pretty", "false",
                "--target", "ES2020",
                "--module", "commonjs",
                "--outDir", str(work_dir),
                str(source),
            ]
        else:
            global_compiler = shutil.which(self.compiler or "tsc")
            if not global_compiler:
                raise RuntimeUnavailableError(
                    "TypeScript execution requires the TypeScript compiler. Run `npm install` in frontend/."
                )
            compile_command = [
                global_compiler,
                "--pretty", "false",
                "--target", "ES2020",
                "--module", "commonjs",
                "--outDir", str(work_dir),
                str(source),
            ]
        return RunnerPlan(source.name, [node, "--no-addons", "--no-warnings", str(output)], compile_command)


class JavaRunner(LanguageRunner):
    def __init__(self, compiler: str | None = None, runtime: str | None = None) -> None:
        self.compiler = compiler
        self.runtime = runtime

    def validate_source(self, code: str) -> None:
        scrubbed = re.sub(
            r'//[^\r\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
            " ",
            code,
            flags=re.DOTALL,
        )
        if re.search(r"\bpackage\s+[A-Za-z_$]", scrubbed):
            raise SourceValidationError(
                "Java package declarations are not supported. Use `public class Main` without a package."
            )
        match = re.search(
            r"\bpublic\s+(?:(?:abstract|final|sealed|non-sealed|strictfp)\s+)*class\s+"
            r"([A-Za-z_$][A-Za-z0-9_$]*)",
            scrubbed,
        )
        if match is None or match.group(1) != "Main":
            raise SourceValidationError(
                "Java source must declare `public class Main` so it matches Main.java."
            )

    def resolve_tools(self) -> tuple[str | None, str | None]:
        """Resolve both JDK tools across Linux Docker and local environments."""

        java_home = os.getenv("JAVA_HOME", "").strip().strip('"')
        java_home_bin = Path(java_home).expanduser() / "bin" if java_home else None

        def resolve_jdk_tool(
            tool_name: str,
            configured: str | None,
            environment_name: str,
        ) -> str | None:
            if configured is not None:
                return _resolve_tool_candidate(configured)

            resolved = _resolve_tool_candidate(os.getenv(environment_name))
            if resolved:
                return resolved
            if java_home_bin:
                java_home_tool = java_home_bin / tool_name
                resolved = _resolve_tool_candidate(java_home_tool)
                if resolved:
                    return resolved
                if os.name == "nt":
                    resolved = _resolve_tool_candidate(java_home_tool.with_suffix(".exe"))
                    if resolved:
                        return resolved
            located = shutil.which(tool_name)
            return str(Path(located).resolve()) if located else None

        java = resolve_jdk_tool("java", self.runtime, "JAVA_EXECUTABLE")
        javac = resolve_jdk_tool("javac", self.compiler, "JAVAC_EXECUTABLE")
        return java, javac

    def plan(self, work_dir: Path) -> RunnerPlan:
        java, javac = self.resolve_tools()
        if java and not javac:
            raise RuntimeUnavailableError(
                "Java JDK compiler (`javac`) is not available. A JRE alone is not enough. "
                "Install a JDK or configure JAVAC_EXECUTABLE, JAVA_HOME, or PATH."
            )
        if not java or not javac:
            raise RuntimeUnavailableError(
                "Java JDK is not available; both `java` and `javac` are required. "
                "Install a JDK or configure "
                "JAVA_EXECUTABLE, JAVAC_EXECUTABLE, JAVA_HOME, or PATH."
            )
        source = work_dir / "Main.java"
        return RunnerPlan(
            source.name,
            [java, "-cp", str(work_dir), "Main"],
            [javac, "-encoding", "UTF-8", str(source)],
        )


class CRunner(LanguageRunner):
    def __init__(self, compiler: str | None = None) -> None:
        self.compiler = compiler

    def resolve_compiler(self) -> str | None:
        if self.compiler is not None:
            return _resolve_tool_candidate(self.compiler)
        configured = _resolve_tool_candidate(os.getenv("GCC_EXECUTABLE"))
        if configured:
            return configured
        path_compiler = _resolve_tool_candidate("gcc")
        if path_compiler:
            return path_compiler
        if os.name == "nt":
            for candidate in WINDOWS_GCC_CANDIDATES:
                resolved = _resolve_tool_candidate(candidate)
                if resolved:
                    return resolved
        return None

    def plan(self, work_dir: Path) -> RunnerPlan:
        compiler = self.resolve_compiler()
        if not compiler:
            raise RuntimeUnavailableError(
                "C compiler unavailable: install GCC (`gcc`) or configure GCC_EXECUTABLE/PATH."
            )
        source = work_dir / "main.c"
        output = work_dir / ("main.exe" if os.name == "nt" else "main")
        return RunnerPlan(
            source.name,
            [str(output)],
            [compiler, str(source), "-o", str(output)],
            (str(Path(compiler).parent),),
        )


class CppRunner(LanguageRunner):
    def __init__(self, compiler: str | None = None) -> None:
        self.compiler = compiler

    def resolve_compiler(self) -> str | None:
        if self.compiler is not None:
            return _resolve_tool_candidate(self.compiler)
        configured = _resolve_tool_candidate(os.getenv("GPP_EXECUTABLE"))
        if configured:
            return configured
        path_compiler = _resolve_tool_candidate("g++")
        if path_compiler:
            return path_compiler
        if os.name == "nt":
            for candidate in WINDOWS_GPP_CANDIDATES:
                resolved = _resolve_tool_candidate(candidate)
                if resolved:
                    return resolved
        return None

    def plan(self, work_dir: Path) -> RunnerPlan:
        compiler = self.resolve_compiler()
        if not compiler:
            raise RuntimeUnavailableError(
                "C++ execution is unavailable because g++ is not installed or not available in PATH."
            )
        source = work_dir / "main.cpp"
        output = work_dir / ("main.exe" if os.name == "nt" else "main")
        return RunnerPlan(
            source.name,
            [str(output)],
            [compiler, str(source), "-o", str(output)],
            (str(Path(compiler).parent),),
        )


class ExecutionService:
    """Compile and execute snippets through language-specific runner plans."""

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        output_limit_bytes: int = DEFAULT_OUTPUT_LIMIT_BYTES,
        max_concurrent_runs: int = DEFAULT_MAX_CONCURRENT_RUNS,
        temp_root: Path | None = None,
        node_executable: str | None = None,
        typescript_compiler: str | None = None,
        java_compiler: str | None = None,
        java_runtime: str | None = None,
        c_compiler: str | None = None,
        cpp_compiler: str | None = None,
        sql_storage_root: Path | None = None,
        sql_row_limit: int = 500,
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
        self._execution_slots = asyncio.Semaphore(max_concurrent_runs)
        self.runners: dict[SupportedLanguage, LanguageRunner] = {
            SupportedLanguage.PYTHON: PythonRunner(),
            SupportedLanguage.JAVASCRIPT: JavaScriptRunner(node_executable),
            SupportedLanguage.TYPESCRIPT: TypeScriptRunner(node_executable, typescript_compiler),
            SupportedLanguage.JAVA: JavaRunner(java_compiler, java_runtime),
            SupportedLanguage.C: CRunner(c_compiler),
            SupportedLanguage.CPP: CppRunner(cpp_compiler),
        }

        self.sql_service = SQLExecutionService(
            sql_storage_root or DEFAULT_SQL_STORAGE_ROOT,
            timeout_seconds=timeout_seconds,
            output_limit_bytes=output_limit_bytes,
            row_limit=sql_row_limit,
        )
        self._runtime_configuration = {
            "node": node_executable or "node",
            "typescript": typescript_compiler,
            "g++": cpp_compiler or "g++",
        }

    async def execute(
        self,
        language: SupportedLanguage,
        code: str,
        stdin: str = "",
        workspace_id: str = "default",
    ) -> ExecutionResult | SQLExecutionResult:
        async with self._execution_slots:
            if language is SupportedLanguage.SQL:
                return await self.sql_service.execute(code, workspace_id)
            return await self._execute_in_temporary_directory(language, code, stdin)

    async def reset_sql(self, workspace_id: str) -> bool:
        async with self._execution_slots:
            return await self.sql_service.reset(workspace_id)

    def runtime_diagnostics(self) -> dict[str, bool]:
        java_runner = self.runners[SupportedLanguage.JAVA]
        c_runner = self.runners[SupportedLanguage.C]
        if not isinstance(java_runner, JavaRunner) or not isinstance(c_runner, CRunner):
            raise RuntimeError("Compiled-language runners are misconfigured.")
        java, javac = java_runner.resolve_tools()
        gcc = c_runner.resolve_compiler()
        return {
            "python": Path(sys.executable).exists(),
            "java": _probe_tool(java, "-version"),
            "javac": _probe_tool(javac, "-version"),
            "gcc": _probe_tool(gcc, "--version"),
        }

    def runtime_status(self) -> dict[str, dict[str, bool | str]]:
        local_typescript = (
            PROJECT_ROOT / "frontend" / "node_modules" / "typescript" / "bin" / "tsc"
        )
        node_available = _tool_is_available(self._runtime_configuration["node"])
        configured_typescript = self._runtime_configuration["typescript"]
        typescript_available = (
            _tool_is_available(configured_typescript)
            if configured_typescript
            else local_typescript.exists() or _tool_is_available("tsc")
        )
        diagnostics = self.runtime_diagnostics()
        cpp_runner = self.runners[SupportedLanguage.CPP]
        cpp_available = (
            bool(cpp_runner.resolve_compiler())
            if isinstance(cpp_runner, CppRunner)
            else False
        )
        java_available = diagnostics["java"] and diagnostics["javac"]
        java_detail = "Ready" if java_available else (
            "JRE detected; JDK compiler missing"
            if diagnostics["java"] and not diagnostics["javac"]
            else "JDK not detected"
        )
        c_available = diagnostics["gcc"]

        def status(available: bool, detail: str | None = None) -> dict[str, bool | str]:
            return {
                "available": available,
                "detail": detail or ("Ready" if available else "Runtime not detected"),
            }

        return {
            SupportedLanguage.PYTHON.value: status(diagnostics["python"]),
            SupportedLanguage.JAVASCRIPT.value: status(node_available),
            SupportedLanguage.TYPESCRIPT.value: status(node_available and typescript_available),
            SupportedLanguage.JAVA.value: status(java_available, java_detail),
            SupportedLanguage.C.value: status(
                c_available,
                "Ready" if c_available else "GCC not detected",
            ),
            SupportedLanguage.CPP.value: status(
                cpp_available
            ),
            SupportedLanguage.SQL.value: status(True),
        }

    async def _execute_in_temporary_directory(
        self, language: SupportedLanguage, code: str, stdin: str
    ) -> ExecutionResult:
        started_at = time.perf_counter()
        temp_parent = str(self.temp_root) if self.temp_root is not None else None
        with tempfile.TemporaryDirectory(prefix="codex-run-", dir=temp_parent) as raw_dir:
            work_dir = Path(raw_dir).resolve()
            runner = self.runners[language]
            plan = runner.plan(work_dir)
            try:
                runner.validate_source(code)
            except SourceValidationError as exc:
                return ExecutionResult(
                    False,
                    "compilation_error",
                    stderr=str(exc),
                    execution_time=time.perf_counter() - started_at,
                )
            source_file = work_dir / plan.source_name
            source_file.write_text(code, encoding="utf-8", newline="\n")
            try:
                source_file.chmod(0o600)
            except OSError:
                pass
            try:
                if plan.compile_command:
                    compile_code, compile_out, compile_err = await self._run_command(
                        plan.compile_command,
                        work_dir,
                        self._build_sanitized_environment(work_dir, plan.compile_command),
                        "",
                    )
                    if compile_code != 0:
                        stderr = self._decode_and_clean_output(
                            compile_err or compile_out, work_dir
                        ) or "Compilation failed."
                        return ExecutionResult(
                            False, "compilation_error", "", stderr, compile_code,
                            time.perf_counter() - started_at,
                        )

                exit_code, stdout_bytes, stderr_bytes = await self._run_command(
                    plan.run_command,
                    work_dir,
                    self._build_sanitized_environment(
                        work_dir,
                        plan.run_command,
                        plan.runtime_path_entries,
                    ),
                    stdin,
                )
            except (FileNotFoundError, PermissionError) as exc:
                raise RuntimeUnavailableError(
                    f"{language.value} execution tool could not be started."
                ) from exc
            except _ExecutionTimedOut:
                return ExecutionResult(
                    False,
                    "timeout",
                    "",
                    f"Execution timed out after {self.timeout_seconds:g} seconds.",
                    None,
                    time.perf_counter() - started_at,
                )
            except _OutputLimitExceeded:
                limit_kib = self.output_limit_bytes / 1024
                return ExecutionResult(
                    False,
                    "output_limit",
                    "",
                    f"Output exceeded the {limit_kib:g} KiB limit.",
                    None,
                    time.perf_counter() - started_at,
                )

            stdout = self._decode_and_clean_output(stdout_bytes, work_dir)
            stderr = self._decode_and_clean_output(stderr_bytes, work_dir)
            elapsed = time.perf_counter() - started_at
            if exit_code == 0:
                return ExecutionResult(True, "success", stdout, stderr, 0, elapsed)
            return ExecutionResult(
                False,
                "runtime_error",
                stdout,
                stderr or f"Process exited with status {exit_code}.",
                exit_code,
                elapsed,
            )

    async def _run_command(
        self,
        command: list[str],
        work_dir: Path,
        environment: dict[str, str],
        stdin: str,
    ) -> tuple[int, bytes, bytes]:
        worker = asyncio.create_task(
            asyncio.to_thread(
                self._run_process_synchronously,
                command,
                work_dir,
                environment,
                stdin,
            )
        )
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError:
            try:
                await asyncio.shield(worker)
            except Exception:
                pass
            raise

    def _run_process_synchronously(
        self,
        command: list[str],
        work_dir: Path,
        environment: dict[str, str],
        stdin: str,
    ) -> tuple[int, bytes, bytes]:
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
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            **process_options,
        )
        if process.stdout is None or process.stderr is None:
            self._terminate_process_tree(process)
            raise RuntimeError("Subprocess output pipes were not created.")
        if process.stdin is not None:
            try:
                process.stdin.write(stdin.encode("utf-8"))
                process.stdin.close()
            except BrokenPipeError:
                pass

        chunks: Queue[tuple[str, bytes | None]] = Queue(maxsize=16)
        stop_readers = threading.Event()
        reader_errors: list[BaseException] = []

        def read_stream(name: str, stream) -> None:
            try:
                while not stop_readers.is_set():
                    chunk = stream.read(READ_CHUNK_BYTES)
                    if not chunk:
                        break
                    while not stop_readers.is_set():
                        try:
                            chunks.put((name, chunk), timeout=0.05)
                            break
                        except Full:
                            continue
            except BaseException as exc:  # pragma: no cover - defensive OS error
                reader_errors.append(exc)
            finally:
                while not stop_readers.is_set():
                    try:
                        chunks.put((name, None), timeout=0.05)
                        break
                    except Full:
                        continue

        readers = [
            threading.Thread(target=read_stream, args=("stdout", process.stdout), daemon=True),
            threading.Thread(target=read_stream, args=("stderr", process.stderr), daemon=True),
        ]
        for reader in readers:
            reader.start()

        stdout = bytearray()
        stderr = bytearray()
        finished_streams = 0
        deadline = time.monotonic() + self.timeout_seconds
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise _ExecutionTimedOut
                try:
                    stream_name, chunk = chunks.get(timeout=min(0.05, remaining))
                except Empty:
                    stream_name, chunk = "", None
                if stream_name and chunk is None:
                    finished_streams += 1
                elif chunk is not None:
                    if len(stdout) + len(stderr) + len(chunk) > self.output_limit_bytes:
                        raise _OutputLimitExceeded
                    (stdout if stream_name == "stdout" else stderr).extend(chunk)
                if finished_streams == 2 and chunks.empty():
                    if reader_errors:
                        raise RuntimeError("Failed to read subprocess output.") from reader_errors[0]
                    return_code = process.poll()
                    if return_code is not None:
                        return return_code, bytes(stdout), bytes(stderr)
        except BaseException:
            if process.poll() is None:
                self._terminate_process_tree(process)
            raise
        finally:
            stop_readers.set()
            for reader in readers:
                reader.join(timeout=1.0)
            process.stdout.close()
            process.stderr.close()
            if process.poll() is None:
                self._terminate_process_tree(process)

    @staticmethod
    def _build_sanitized_environment(
        work_dir: Path,
        command: list[str] | None = None,
        extra_path_entries: tuple[str, ...] = (),
    ) -> dict[str, str]:
        work_dir_text = str(work_dir)
        path_entries = [work_dir_text]
        if command:
            executable = Path(command[0])
            if executable.is_absolute():
                path_entries.append(str(executable.parent))
        path_entries.extend(extra_path_entries)
        environment = {
            "HOME": work_dir_text,
            "USERPROFILE": work_dir_text,
            "TMPDIR": work_dir_text,
            "TMP": work_dir_text,
            "TEMP": work_dir_text,
            "PATH": os.pathsep.join(dict.fromkeys(path_entries)),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "NO_COLOR": "1",
            "CODEX_RUNNER": "development-only",
        }
        if os.name == "nt":
            system_root = os.environ.get("SystemRoot", r"C:\Windows")
            environment["SystemRoot"] = system_root
            environment["WINDIR"] = system_root
            environment["COMSPEC"] = str(Path(system_root) / "System32" / "cmd.exe")
        return environment

    @staticmethod
    def _requires_threaded_subprocess() -> bool:
        return True

    @staticmethod
    def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        if os.name == "nt":
            taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"
            if taskkill.exists():
                try:
                    subprocess.run(
                        [str(taskkill), "/PID", str(process.pid), "/T", "/F"],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=1,
                        check=False,
                    )
                except (OSError, subprocess.TimeoutExpired):
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
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass

    @staticmethod
    def _decode_and_clean_output(raw_output: bytes, work_dir: Path) -> str:
        output = raw_output.decode("utf-8", errors="replace")
        work_dir_text = str(work_dir)
        output = output.replace(work_dir_text, "<sandbox>")
        output = output.replace(work_dir_text.replace("\\", "/"), "<sandbox>")
        return output.rstrip("\r\n")
