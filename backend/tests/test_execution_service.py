import asyncio
import os
from pathlib import Path
import shutil
import sqlite3
import sys

import pytest

import backend.services.execution_service as execution_module
from backend.models.code_request import SupportedLanguage
from backend.services.execution_service import (
    CppRunner,
    CRunner,
    ExecutionService,
    JavaRunner,
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


@pytest.mark.asyncio
async def test_python_stdin_and_structured_result() -> None:
    result = await ExecutionService().execute(
        SupportedLanguage.PYTHON,
        "name = input()\nprint(f'Hello {name}')",
        "CodeX\n",
    )

    assert result.success is True
    assert result.status == "success"
    assert result.stdout == "Hello CodeX"
    assert result.stderr == ""
    assert result.exit_code == 0
    assert result.execution_time > 0
    assert result.memory_usage is None


@pytest.mark.asyncio
async def test_python_multiple_stdin_values() -> None:
    result = await ExecutionService().execute(
        SupportedLanguage.PYTHON,
        'a = int(input("Enter first number: "))\nb = int(input("Enter second number: "))\nprint("Sum =", a + b)',
        "10\n20\n",
    )

    assert result.success is True
    assert result.stdout == "Enter first number: Enter second number: Sum = 30"


@pytest.mark.asyncio
async def test_python_empty_stdin_has_helpful_input_message() -> None:
    result = await ExecutionService().execute(
        SupportedLanguage.PYTHON,
        "value = input()\nprint(value)",
    )

    assert result.success is False
    assert result.status == "runtime_error"
    assert result.stderr == "Program input is required. Enter input in the Program Input panel and run again."


@pytest.mark.asyncio
async def test_javascript_stdin() -> None:
    if shutil.which("node") is None:
        pytest.skip("Node.js is not installed")
    result = await ExecutionService().execute(
        SupportedLanguage.JAVASCRIPT,
        "process.stdin.on('data', data => console.log('Hello ' + data.toString().trim()));",
        "CodeX\n",
    )
    assert result.success is True
    assert result.stdout == "Hello CodeX"


@pytest.mark.asyncio
async def test_javascript_multiple_stdin_values() -> None:
    if shutil.which("node") is None:
        pytest.skip("Node.js is not installed")
    result = await ExecutionService().execute(
        SupportedLanguage.JAVASCRIPT,
        "let values = []; process.stdin.on('data', data => values.push(...data.toString().trim().split(/\\s+/).map(Number))); process.stdin.on('end', () => console.log('Sum =', values[0] + values[1]));",
        "10\n20\n",
    )
    assert result.success is True
    assert result.stdout == "Sum = 30"


@pytest.mark.asyncio
async def test_typescript_compiles_and_runs() -> None:
    compiler = Path(__file__).resolve().parents[2] / "frontend" / "node_modules" / "typescript" / "bin" / "tsc"
    if shutil.which("node") is None or not compiler.exists():
        pytest.skip("Project-local TypeScript tooling is not installed")
    result = await ExecutionService().execute(
        SupportedLanguage.TYPESCRIPT,
        'const language: string = "TypeScript";\nconsole.log(language + " works");',
    )
    assert result.success is True
    assert result.stdout == "TypeScript works"


@pytest.mark.asyncio
async def test_typescript_stdin() -> None:
    compiler = Path(__file__).resolve().parents[2] / "frontend" / "node_modules" / "typescript" / "bin" / "tsc"
    if shutil.which("node") is None or not compiler.exists():
        pytest.skip("Project-local TypeScript tooling is not installed")
    result = await ExecutionService().execute(
        SupportedLanguage.TYPESCRIPT,
        'const nodeProcess = (globalThis as any).process;\nnodeProcess.stdin.on("data", (data: any) => console.log("Hello " + data.toString().trim()));',
        "CodeX\n",
    )
    assert result.success is True
    assert result.stdout == "Hello CodeX"


@pytest.mark.asyncio
async def test_typescript_compilation_error_is_separate() -> None:
    compiler = Path(__file__).resolve().parents[2] / "frontend" / "node_modules" / "typescript" / "bin" / "tsc"
    if shutil.which("node") is None or not compiler.exists():
        pytest.skip("Project-local TypeScript tooling is not installed")
    result = await ExecutionService().execute(
        SupportedLanguage.TYPESCRIPT,
        "const value: string = 42;",
    )
    assert result.success is False
    assert result.status == "compilation_error"
    assert result.exit_code != 0
    assert "not assignable" in result.stderr


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("language", "keyword", "overrides"),
    [
        (SupportedLanguage.JAVA, "javac", {"java_compiler": os.path.join("missing", "javac")}),
        (SupportedLanguage.C, "gcc", {"c_compiler": os.path.join("missing", "gcc")}),
        (SupportedLanguage.CPP, "g++", {"cpp_compiler": os.path.join("missing", "g++")}),
    ],
)
async def test_missing_compilers_have_actionable_errors(language, keyword, overrides) -> None:
    with pytest.raises(RuntimeUnavailableError, match=keyword):
        await ExecutionService(**overrides).execute(language, "placeholder")


@pytest.mark.asyncio
async def test_java_requires_public_main_before_compilation() -> None:
    result = await ExecutionService(
        java_compiler=sys.executable,
        java_runtime=sys.executable,
    ).execute(
        SupportedLanguage.JAVA,
        "public class Example { public static void main(String[] args) {} }",
    )

    assert result.success is False
    assert result.status == "compilation_error"
    assert "public class Main" in result.stderr


@pytest.mark.asyncio
async def test_c_compiles_runs_and_accepts_stdin_when_gcc_is_available() -> None:
    if not ExecutionService().runtime_diagnostics()["gcc"]:
        pytest.skip("GCC is not installed")
    result = await ExecutionService().execute(
        SupportedLanguage.C,
        '#include <stdio.h>\nint main(void) { int a, b; scanf("%d %d", &a, &b); printf("%d\\n", a + b); }',
        "10\n20\n",
    )

    assert result.success is True
    assert result.stdout == "30"


@pytest.mark.asyncio
async def test_c_runs_hello_world_when_gcc_is_available() -> None:
    if not ExecutionService().runtime_diagnostics()["gcc"]:
        pytest.skip("GCC is not installed")
    result = await ExecutionService().execute(
        SupportedLanguage.C,
        '#include <stdio.h>\nint main(void) { printf("C works\\n"); return 0; }',
    )

    assert result.success is True
    assert result.stdout == "C works"


@pytest.mark.asyncio
async def test_c_returns_real_compiler_errors_when_gcc_is_available() -> None:
    if not ExecutionService().runtime_diagnostics()["gcc"]:
        pytest.skip("GCC is not installed")
    result = await ExecutionService().execute(
        SupportedLanguage.C,
        "int main(void) { this is not valid C; }",
    )

    assert result.success is False
    assert result.status == "compilation_error"
    assert result.exit_code != 0
    assert result.stderr


@pytest.mark.asyncio
async def test_java_compiles_runs_and_accepts_stdin_when_jdk_is_available() -> None:
    diagnostics = ExecutionService().runtime_diagnostics()
    if not diagnostics["javac"] or not diagnostics["java"]:
        pytest.skip("A JDK is not installed")
    result = await ExecutionService().execute(
        SupportedLanguage.JAVA,
        """import java.util.Scanner;
public class Main {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        int a = scanner.nextInt();
        int b = scanner.nextInt();
        System.out.println("Sum = " + (a + b));
    }
}""",
        "10\n20\n",
    )

    assert result.success is True
    assert result.stdout == "Sum = 30"


@pytest.mark.asyncio
async def test_java_runs_hello_world_when_jdk_is_available() -> None:
    diagnostics = ExecutionService().runtime_diagnostics()
    if not diagnostics["javac"] or not diagnostics["java"]:
        pytest.skip("A JDK is not installed")
    result = await ExecutionService().execute(
        SupportedLanguage.JAVA,
        """public class Main {
    public static void main(String[] args) {
        System.out.println("Java works");
    }
}""",
    )

    assert result.success is True
    assert result.stdout == "Java works"


@pytest.mark.asyncio
async def test_java_returns_real_compiler_errors_when_jdk_is_available() -> None:
    diagnostics = ExecutionService().runtime_diagnostics()
    if not diagnostics["javac"] or not diagnostics["java"]:
        pytest.skip("A JDK is not installed")
    result = await ExecutionService().execute(
        SupportedLanguage.JAVA,
        "public class Main { public static void main(String[] args) { missing; } }",
    )

    assert result.success is False
    assert result.status == "compilation_error"
    assert result.exit_code != 0
    assert "error" in result.stderr.lower()


@pytest.mark.asyncio
async def test_sql_multiple_statements_return_structured_rows(tmp_path: Path) -> None:
    service = ExecutionService(sql_storage_root=tmp_path)
    result = await service.execute(
        SupportedLanguage.SQL,
        """CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT);
INSERT INTO notes (body) VALUES ('semi;colon'), ('second');
SELECT id, body FROM notes ORDER BY id;""",
        workspace_id="workspace-one",
    )

    assert result.success is True
    assert result.columns == ["id", "body"]
    assert result.rows == [[1, "semi;colon"], [2, "second"]]
    assert result.row_count == 2


@pytest.mark.asyncio
async def test_sql_persists_per_workspace_and_reset_is_scoped(tmp_path: Path) -> None:
    service = ExecutionService(sql_storage_root=tmp_path)
    created = await service.execute(
        SupportedLanguage.SQL,
        "CREATE TABLE values_table (value TEXT); INSERT INTO values_table VALUES ('kept');",
        workspace_id="workspace-one",
    )
    persisted = await service.execute(
        SupportedLanguage.SQL,
        "SELECT value FROM values_table;",
        workspace_id="workspace-one",
    )
    isolated = await service.execute(
        SupportedLanguage.SQL,
        "SELECT value FROM values_table;",
        workspace_id="workspace-two",
    )
    removed = await service.reset_sql("workspace-one")
    after_reset = await service.execute(
        SupportedLanguage.SQL,
        "SELECT value FROM values_table;",
        workspace_id="workspace-one",
    )

    assert created.success is True
    assert persisted.rows == [["kept"]]
    assert isolated.status == "sql_error"
    assert removed is True
    assert after_reset.status == "sql_error"


@pytest.mark.asyncio
async def test_sql_cannot_attach_or_read_the_application_database(tmp_path: Path) -> None:
    application_database = tmp_path / "application.db"
    with sqlite3.connect(application_database) as connection:
        connection.execute("CREATE TABLE secrets (value TEXT)")
        connection.execute("INSERT INTO secrets VALUES ('must-not-leak')")
        connection.commit()

    service = ExecutionService(sql_storage_root=tmp_path / "playgrounds")
    escaped_path = str(application_database).replace("'", "''")
    result = await service.execute(
        SupportedLanguage.SQL,
        f"ATTACH DATABASE '{escaped_path}' AS application; SELECT * FROM application.secrets;",
        workspace_id="workspace-one",
    )

    assert result.success is False
    assert result.status == "sql_error"
    assert "not allowed" in result.stderr


@pytest.mark.asyncio
async def test_sql_vacuum_into_cannot_write_outside_the_playground(tmp_path: Path) -> None:
    service = ExecutionService(sql_storage_root=tmp_path / "playgrounds")
    escaped_file = tmp_path / "escaped.db"
    sql_path = escaped_file.as_posix().replace("'", "''")

    result = await service.execute(
        SupportedLanguage.SQL,
        f"VACUUM INTO '{sql_path}';",
        workspace_id="workspace-one",
    )

    assert result.success is False
    assert escaped_file.exists() is False


@pytest.mark.asyncio
async def test_sql_syntax_errors_are_returned_without_partial_changes(tmp_path: Path) -> None:
    service = ExecutionService(sql_storage_root=tmp_path)
    result = await service.execute(
        SupportedLanguage.SQL,
        "CREATE TABLE rolled_back (id INTEGER); INSERT broken syntax;",
        workspace_id="workspace-one",
    )
    follow_up = await service.execute(
        SupportedLanguage.SQL,
        "SELECT * FROM rolled_back;",
        workspace_id="workspace-one",
    )

    assert result.success is False
    assert result.status == "sql_error"
    assert "syntax" in result.stderr.lower()
    assert follow_up.success is False
    assert "no such table" in follow_up.stderr.lower()


def test_runtime_status_reports_every_backend_language() -> None:
    runtimes = ExecutionService().runtime_status()

    assert set(runtimes) == {language.value for language in SupportedLanguage}
    assert runtimes["python"]["available"] is True
    assert runtimes["sql"]["available"] is True
    assert isinstance(runtimes["c"]["available"], bool)
    assert isinstance(runtimes["java"]["available"], bool)


def test_java_environment_overrides_take_precedence(tmp_path: Path, monkeypatch) -> None:
    configured_java = tmp_path / "configured" / "java.exe"
    configured_javac = tmp_path / "configured" / "javac.exe"
    java_home = tmp_path / "jdk"
    configured_java.parent.mkdir(parents=True)
    configured_java.touch()
    configured_javac.touch()
    (java_home / "bin").mkdir(parents=True)
    (java_home / "bin" / "java.exe").touch()
    (java_home / "bin" / "javac.exe").touch()
    monkeypatch.setenv("JAVA_EXECUTABLE", str(configured_java))
    monkeypatch.setenv("JAVAC_EXECUTABLE", str(configured_javac))
    monkeypatch.setenv("JAVA_HOME", str(java_home))

    java, javac = JavaRunner().resolve_tools()

    assert java == str(configured_java.resolve())
    assert javac == str(configured_javac.resolve())


def test_java_home_is_used_when_java_is_not_on_path(tmp_path: Path, monkeypatch) -> None:
    java_home = tmp_path / "jdk"
    suffix = ".exe" if os.name == "nt" else ""
    java = java_home / "bin" / f"java{suffix}"
    javac = java_home / "bin" / f"javac{suffix}"
    java.parent.mkdir(parents=True)
    java.touch()
    javac.touch()
    monkeypatch.delenv("JAVA_EXECUTABLE", raising=False)
    monkeypatch.delenv("JAVAC_EXECUTABLE", raising=False)
    monkeypatch.setenv("JAVA_HOME", str(java_home))
    monkeypatch.setattr(execution_module.shutil, "which", lambda _command: None)

    resolved_java, resolved_javac = JavaRunner().resolve_tools()

    assert resolved_java == str(java.resolve())
    assert resolved_javac == str(javac.resolve())


def test_jre_without_javac_returns_the_required_jdk_message(tmp_path: Path) -> None:
    java = tmp_path / "java.exe"
    java.touch()

    with pytest.raises(RuntimeUnavailableError, match="A JRE alone is not enough"):
        JavaRunner(compiler=str(tmp_path / "missing-javac.exe"), runtime=str(java)).plan(tmp_path)


def test_gcc_environment_override_is_resolved(tmp_path: Path, monkeypatch) -> None:
    gcc = tmp_path / "toolchain" / "gcc.exe"
    gcc.parent.mkdir(parents=True)
    gcc.touch()
    monkeypatch.setenv("GCC_EXECUTABLE", str(gcc))

    assert CRunner().resolve_compiler() == str(gcc.resolve())


@pytest.mark.skipif(os.name != "nt", reason="Windows-only common GCC locations")
def test_common_windows_gcc_location_is_detected(tmp_path: Path, monkeypatch) -> None:
    gcc = tmp_path / "msys64" / "ucrt64" / "bin" / "gcc.exe"
    gcc.parent.mkdir(parents=True)
    gcc.touch()
    monkeypatch.delenv("GCC_EXECUTABLE", raising=False)
    monkeypatch.setattr(execution_module.shutil, "which", lambda _command: None)
    monkeypatch.setattr(execution_module, "WINDOWS_GCC_CANDIDATES", (gcc,))

    assert CRunner().resolve_compiler() == str(gcc.resolve())


@pytest.mark.skipif(os.name != "nt", reason="Windows-only common GCC locations")
def test_common_windows_gpp_location_is_detected(tmp_path: Path, monkeypatch) -> None:
    gpp = tmp_path / "msys64" / "ucrt64" / "bin" / "g++.exe"
    gpp.parent.mkdir(parents=True)
    gpp.touch()
    monkeypatch.delenv("GPP_EXECUTABLE", raising=False)
    monkeypatch.setattr(execution_module.shutil, "which", lambda _command: None)
    monkeypatch.setattr(execution_module, "WINDOWS_GPP_CANDIDATES", (gpp,))

    assert CppRunner().resolve_compiler() == str(gpp.resolve())


@pytest.mark.asyncio
async def test_cpp_compiles_runs_and_accepts_stdin_when_gpp_is_available() -> None:
    compiler = CppRunner().resolve_compiler()
    if not compiler:
        pytest.skip("g++ is not installed")
    result = await ExecutionService().execute(
        SupportedLanguage.CPP,
        "#include <iostream>\nint main() { int a, b; std::cin >> a >> b; std::cout << a + b; return 0; }",
        "10\n20\n",
    )

    assert result.success is True
    assert result.stdout == "30"


def test_runtime_status_refreshes_environment_without_recreating_service(
    tmp_path: Path,
    monkeypatch,
) -> None:
    java = tmp_path / "java.exe"
    javac = tmp_path / "javac.exe"
    gcc = tmp_path / "gcc.exe"
    for executable in (java, javac, gcc):
        executable.touch()
    service = ExecutionService()
    monkeypatch.setenv("JAVA_EXECUTABLE", str(java))
    monkeypatch.setenv("JAVAC_EXECUTABLE", str(javac))
    monkeypatch.setenv("GCC_EXECUTABLE", str(gcc))
    monkeypatch.setattr(execution_module, "_probe_tool", lambda executable, _argument: bool(executable))

    statuses = service.runtime_status()

    assert statuses["java"]["available"] is True
    assert statuses["c"]["available"] is True


def test_compiled_language_plans_use_correct_files_and_stages(tmp_path: Path) -> None:
    executable = sys.executable
    java = JavaRunner(executable, executable).plan(tmp_path)
    c = CRunner(executable).plan(tmp_path)
    cpp = CppRunner(executable).plan(tmp_path)

    assert java.source_name == "Main.java"
    assert "Main" == java.run_command[-1]
    assert java.compile_command[-1].endswith("Main.java")
    assert c.source_name == "main.c"
    assert c.compile_command[1].endswith("main.c")
    assert cpp.source_name == "main.cpp"
    assert cpp.compile_command[1].endswith("main.cpp")
    assert c.run_command[0].endswith("main.exe" if os.name == "nt" else "main")
    assert str(Path(executable).parent) in c.runtime_path_entries
    assert str(Path(executable).parent) in cpp.runtime_path_entries
