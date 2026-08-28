"""Isolated SQLite playground execution for user-authored SQL.

Playground databases live in a dedicated directory and are addressed only by a
SHA-256 digest of the client workspace ID. They are never connected to the
application database. SQLite's authorizer rejects operations that could attach
another database, alter connection settings, load extensions, or create virtual
tables/triggers.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Final

DEFAULT_SQL_ROW_LIMIT: Final[int] = 500
MAX_SQL_STATEMENTS: Final[int] = 100


@dataclass(frozen=True, slots=True)
class SQLExecutionResult:
    success: bool
    status: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    execution_time: float = 0.0
    memory_usage: float | None = None
    columns: list[str] | None = None
    rows: list[list[Any]] | None = None
    row_count: int | None = None
    message: str | None = None

    @property
    def output(self) -> str | None:
        return self.stdout if self.success else None

    @property
    def error(self) -> str | None:
        return self.stderr if not self.success else None


class _SQLLimitExceeded(Exception):
    pass


class SQLExecutionService:
    """Execute SQL against persistent, isolated playground databases."""

    def __init__(
        self,
        storage_root: Path,
        *,
        timeout_seconds: float,
        output_limit_bytes: int,
        row_limit: int = DEFAULT_SQL_ROW_LIMIT,
    ) -> None:
        if row_limit <= 0:
            raise ValueError("row_limit must be positive")
        self.storage_root = storage_root.resolve()
        self.timeout_seconds = timeout_seconds
        self.output_limit_bytes = output_limit_bytes
        self.row_limit = row_limit

    async def execute(self, code: str, workspace_id: str) -> SQLExecutionResult:
        return await asyncio.to_thread(self._execute_synchronously, code, workspace_id)

    async def reset(self, workspace_id: str) -> bool:
        return await asyncio.to_thread(self._reset_synchronously, workspace_id)

    def database_path(self, workspace_id: str) -> Path:
        digest = hashlib.sha256(workspace_id.encode("utf-8")).hexdigest()
        return self.storage_root / f"{digest}.db"

    def _execute_synchronously(self, code: str, workspace_id: str) -> SQLExecutionResult:
        started_at = time.perf_counter()
        try:
            statements = self._split_statements(code)
        except sqlite3.Error as exc:
            return self._error_result(str(exc), started_at)
        if not statements:
            return self._error_result("SQL must contain at least one statement.", started_at)
        if len(statements) > MAX_SQL_STATEMENTS:
            return self._error_result(
                f"SQL scripts are limited to {MAX_SQL_STATEMENTS} statements.",
                started_at,
                status="output_limit",
            )

        self.storage_root.mkdir(parents=True, exist_ok=True)
        database_path = self.database_path(workspace_id)
        connection = sqlite3.connect(
            database_path,
            timeout=min(self.timeout_seconds, 5.0),
            isolation_level=None,
        )
        deadline = time.monotonic() + self.timeout_seconds
        connection.set_progress_handler(
            lambda: 1 if time.monotonic() >= deadline else 0,
            1_000,
        )

        final_columns: list[str] | None = None
        final_rows: list[list[Any]] | None = None
        final_row_count: int | None = None
        affected_rows = 0
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.set_authorizer(self._authorize)
            for statement in statements:
                cursor = connection.execute(statement)
                if cursor.description:
                    fetched = cursor.fetchmany(self.row_limit + 1)
                    if len(fetched) > self.row_limit:
                        raise _SQLLimitExceeded(
                            f"Query returned more than the {self.row_limit}-row limit."
                        )
                    final_columns = [column[0] for column in cursor.description]
                    final_rows = [
                        [self._json_value(value) for value in row]
                        for row in fetched
                    ]
                    final_row_count = len(final_rows)
                    encoded_size = len(
                        json.dumps(
                            {"columns": final_columns, "rows": final_rows},
                            ensure_ascii=False,
                        ).encode("utf-8")
                    )
                    if encoded_size > self.output_limit_bytes:
                        raise _SQLLimitExceeded(
                            f"Query result exceeded the {self.output_limit_bytes / 1024:g} KiB output limit."
                        )
                elif cursor.rowcount > 0:
                    affected_rows += cursor.rowcount

            connection.set_authorizer(None)
            connection.commit()
        except _SQLLimitExceeded as exc:
            connection.set_authorizer(None)
            connection.rollback()
            return self._error_result(str(exc), started_at, status="output_limit")
        except sqlite3.Error as exc:
            connection.set_authorizer(None)
            connection.rollback()
            message = str(exc)
            if "interrupted" in message.lower() and time.monotonic() >= deadline:
                message = f"SQL execution timed out after {self.timeout_seconds:g} seconds."
                status = "timeout"
            else:
                status = "sql_error"
                if "not authorized" in message.lower():
                    message = (
                        "This statement is not allowed in the isolated SQL playground. "
                        "ATTACH, DETACH, PRAGMA, transaction control, extensions, triggers, "
                        "and virtual tables are blocked."
                    )
            return self._error_result(message, started_at, status=status)
        finally:
            connection.close()

        if final_columns is not None:
            message = f"Query returned {final_row_count} row(s)."
        elif affected_rows:
            message = (
                f"Executed {len(statements)} statement(s); "
                f"{affected_rows} row(s) affected."
            )
            final_row_count = affected_rows
        else:
            message = f"Executed {len(statements)} statement(s) successfully."
            final_row_count = 0

        return SQLExecutionResult(
            success=True,
            status="success",
            stdout=message,
            exit_code=0,
            execution_time=time.perf_counter() - started_at,
            columns=final_columns,
            rows=final_rows,
            row_count=final_row_count,
            message=message,
        )

    def _reset_synchronously(self, workspace_id: str) -> bool:
        database_path = self.database_path(workspace_id)
        removed = False
        for suffix in ("", "-journal", "-shm", "-wal"):
            candidate = Path(f"{database_path}{suffix}")
            try:
                candidate.unlink()
                removed = True
            except FileNotFoundError:
                pass
        return removed

    @staticmethod
    def _split_statements(script: str) -> list[str]:
        """Split only where SQLite confirms a statement is syntactically complete."""

        statements: list[str] = []
        buffer: list[str] = []
        for character in script:
            buffer.append(character)
            if character == ";":
                candidate = "".join(buffer)
                if sqlite3.complete_statement(candidate):
                    if candidate.strip():
                        statements.append(candidate)
                    buffer.clear()

        trailing = "".join(buffer).strip()
        if trailing:
            candidate = trailing if trailing.endswith(";") else f"{trailing};"
            if not sqlite3.complete_statement(candidate):
                raise sqlite3.OperationalError("incomplete SQL statement")
            statements.append(trailing)
        return statements

    @staticmethod
    def _authorize(
        action: int,
        first_argument: str | None,
        second_argument: str | None,
        _database_name: str | None,
        _trigger_name: str | None,
    ) -> int:
        denied_actions = {
            sqlite3.SQLITE_ATTACH,
            sqlite3.SQLITE_DETACH,
            sqlite3.SQLITE_PRAGMA,
            sqlite3.SQLITE_TRANSACTION,
            sqlite3.SQLITE_CREATE_TRIGGER,
            sqlite3.SQLITE_DROP_TRIGGER,
            sqlite3.SQLITE_CREATE_VTABLE,
            sqlite3.SQLITE_DROP_VTABLE,
        }
        if action in denied_actions:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_FUNCTION:
            function_name = (second_argument or first_argument or "").lower()
            if function_name == "load_extension":
                return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    @staticmethod
    def _json_value(value: Any) -> Any:
        if isinstance(value, bytes):
            return f"0x{value.hex()}"
        return value

    @staticmethod
    def _error_result(
        message: str,
        started_at: float,
        *,
        status: str = "sql_error",
    ) -> SQLExecutionResult:
        return SQLExecutionResult(
            success=False,
            status=status,
            stderr=message,
            execution_time=time.perf_counter() - started_at,
            message=message,
        )
