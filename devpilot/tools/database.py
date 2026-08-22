"""Read-only SQLite inspection. No database URL or credentials are accepted."""
import sqlite3
import time
from urllib.parse import quote

from ..safety import Workspace, SafetyError, redact

SAFE_FUNCTIONS = {"count", "sum", "avg", "min", "max", "total", "coalesce", "ifnull", "nullif",
                  "lower", "upper", "trim", "ltrim", "rtrim", "length", "round", "abs", "substr",
                  "substring", "date", "strftime", "typeof"}


def query(workspace: Workspace, path: str, sql: str, limit: int = 50) -> dict:
    file = workspace.path(path)
    if file.suffix not in {".db", ".sqlite", ".sqlite3"} or not file.is_file():
        raise SafetyError("Choose a SQLite file inside the workspace")
    if file.stat().st_size > 120_000:
        raise SafetyError("Database exceeds this demo's size budget")
    uri = "file:" + quote(str(file), safe="/") + "?mode=ro"
    db = sqlite3.connect(uri, uri=True, timeout=1)
    try:
        db.enable_load_extension(False)
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1_000_000)
        db.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 8_000)
        db.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, 100)
        db.setlimit(sqlite3.SQLITE_LIMIT_EXPR_DEPTH, 30)
        deadline = time.monotonic() + 0.3
        db.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)

        def authorize(action, arg1, arg2, database, source):
            if action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_RECURSIVE}:
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in SAFE_FUNCTIONS:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY

        db.set_authorizer(authorize)
        cursor = db.execute(sql)
        if cursor.description is None:
            raise SafetyError("Only result-producing read queries are supported")
        records = cursor.fetchmany(limit + 1)
        def cell(value):
            if isinstance(value, bytes):
                return f"[binary: {len(value)} bytes]"
            if isinstance(value, str):
                return redact(value[:1000])
            return value
        return {"columns": [d[0] for d in cursor.description],
                "rows": [[cell(v) for v in row] for row in records[:limit]],
                "truncated": len(records) > limit, "read_only": True}
    finally:
        db.close()
