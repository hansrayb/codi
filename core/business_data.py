"""Read-only business data and project logic inspection helpers."""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from html import escape
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from config import Settings
from models.result import MessagePayload
from utils.formatter import format_error_payload

SQLITE_EXTENSIONS = {".db", ".sqlite", ".sqlite3"}
MAX_DISCOVERED_DATABASES = 8
MAX_SQL_ROWS = 20
MAX_SCHEMA_COLUMNS = 500
MAX_CELL_LENGTH = 120
MAX_LOGIC_FILES = 12
MAX_SCAN_FILES = 600
MAX_SCAN_BYTES = 120_000

DATABASE_KEYWORDS = (
    "database",
    "db",
    "data bisnis",
    "schema",
    "skema",
    "tabel",
    "table",
    "select ",
    "with ",
    "pragma ",
    "hitung ",
    "jumlah ",
    "postgres",
    "postgresql",
    "mysql",
)
LOGIC_KEYWORDS = (
    "logika bisnis",
    "business logic",
    "alur bisnis",
    "aturan bisnis",
    "rule bisnis",
    "rules bisnis",
    "business rule",
    "business rules",
)
SCHEMA_KEYWORDS = ("schema", "skema", "struktur", "tabel", "table", "database", "db")
LOGIC_FILE_MARKERS = (
    "service",
    "usecase",
    "use_case",
    "business",
    "domain",
    "model",
    "entity",
    "controller",
    "route",
    "handler",
    "workflow",
    "policy",
    "rule",
    "validation",
    "validator",
    "schema",
    "migration",
)
LOGIC_EXTENSIONS = {
    ".cs",
    ".go",
    ".java",
    ".js",
    ".jsx",
    ".php",
    ".prisma",
    ".py",
    ".rb",
    ".sql",
    ".ts",
    ".tsx",
}
SKIP_DIR_NAMES = {
    ".cache",
    ".git",
    ".hg",
    ".idea",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "out",
    "target",
    "vendor",
    "venv",
}
SELECT_SQL = re.compile(r"^\s*(?:select|with)\b", re.IGNORECASE | re.DOTALL)
PRAGMA_SQL = re.compile(r"^\s*pragma\s+(?:table_info|table_xinfo|index_list|foreign_key_list)\s*\(", re.IGNORECASE)
FORBIDDEN_SQL = re.compile(
    r"\b(?:insert|update|delete|drop|alter|create|replace|truncate|attach|detach|vacuum|reindex)\b",
    re.IGNORECASE,
)
COUNT_INTENT = re.compile(r"\b(?:hitung|jumlah|count)\s+(?:data\s+)?(?:di\s+)?(?:tabel\s+|table\s+)?(?P<table>[a-zA-Z_][a-zA-Z0-9_]*)\b", re.IGNORECASE)
SHOW_TABLE_INTENT = re.compile(r"\b(?:lihat|tampilkan|show|preview)\s+(?:data\s+)?(?:tabel\s+|table\s+)(?P<table>[a-zA-Z_][a-zA-Z0-9_]*)\b", re.IGNORECASE)


@dataclass(frozen=True)
class BusinessDataRequest:
    """Classified read-only business data request."""

    kind: str
    sql: str | None = None
    engine_hint: str | None = None


@dataclass(frozen=True)
class DatabaseTarget:
    """A configured or discovered database target."""

    kind: str
    label: str
    path: Path | None = None
    url: str | None = None


@dataclass(frozen=True)
class LogicFileSummary:
    """A likely business-logic source file."""

    path: Path
    score: int
    line_count: int
    symbols: tuple[str, ...]


class BusinessDataService:
    """Serve read-only database and business-logic summaries for a project."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def match(self, text: str) -> BusinessDataRequest | None:
        """Return a classified business-data request, if this text is one."""

        normalized = _normalize(text)
        if not normalized:
            return None
        engine_hint = _extract_engine_hint(normalized)
        if any(keyword in normalized for keyword in LOGIC_KEYWORDS):
            return BusinessDataRequest(kind="logic")

        sql = _extract_sql(text)
        if sql is not None:
            return BusinessDataRequest(kind="sql", sql=sql, engine_hint=engine_hint)

        count_match = COUNT_INTENT.search(text)
        if count_match:
            table = count_match.group("table")
            return BusinessDataRequest(
                kind="sql",
                sql=f'SELECT COUNT(*) AS total FROM "{table}"',
                engine_hint=engine_hint,
            )

        show_match = SHOW_TABLE_INTENT.search(text)
        if show_match:
            table = show_match.group("table")
            return BusinessDataRequest(
                kind="sql",
                sql=f'SELECT * FROM "{table}" LIMIT {MAX_SQL_ROWS}',
                engine_hint=engine_hint,
            )

        if any(keyword in normalized for keyword in SCHEMA_KEYWORDS) and any(
            keyword in normalized for keyword in DATABASE_KEYWORDS
        ):
            return BusinessDataRequest(kind="schema", engine_hint=engine_hint)
        return None

    def handle(self, request: BusinessDataRequest, repo_root: Path, *, assistant_name: str) -> MessagePayload:
        """Return a Telegram payload for the request."""

        root = repo_root.resolve()
        if request.kind == "logic":
            return self._render_logic_summary(root, assistant_name=assistant_name)
        if request.kind == "schema":
            databases = self._find_database_targets(root, request.engine_hint)
            if not databases:
                return format_error_payload(
                    self._build_no_database_message(request.engine_hint),
                    assistant_name=assistant_name,
                )
            return self._render_schema(databases, assistant_name=assistant_name)
        if request.kind == "sql" and request.sql:
            databases = self._find_database_targets(root, request.engine_hint)
            if not databases:
                return format_error_payload(
                    self._build_no_database_message(request.engine_hint),
                    assistant_name=assistant_name,
                )
            return self._run_sql(databases[0], request.sql, assistant_name=assistant_name)
        return format_error_payload("Request bisnis ini belum dikenali.", assistant_name=assistant_name)

    def _find_database_targets(
        self,
        repo_root: Path,
        engine_hint: str | None,
    ) -> tuple[DatabaseTarget, ...]:
        targets: list[DatabaseTarget] = []
        for url in getattr(self._settings, "business_database_urls", ()):
            target = _database_target_from_url(url)
            if target is not None and _target_matches_hint(target, engine_hint):
                targets.append(target)
        if engine_hint in {"postgresql", "mysql"}:
            return tuple(targets)
        targets.extend(
            DatabaseTarget(kind="sqlite", label=str(path), path=path)
            for path in self._find_sqlite_databases(repo_root)
            if _target_matches_hint(DatabaseTarget(kind="sqlite", label=str(path), path=path), engine_hint)
        )
        return tuple(targets)

    def _find_sqlite_databases(self, repo_root: Path) -> tuple[Path, ...]:
        configured = tuple(
            path
            for path in getattr(self._settings, "business_database_paths", ())
            if path.exists() and path.is_file() and _is_within(path, repo_root)
        )
        discovered: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(repo_root, topdown=True):
            dirnames[:] = [dirname for dirname in dirnames if dirname not in SKIP_DIR_NAMES]
            dirnames.sort()
            for filename in sorted(filenames):
                candidate = Path(dirpath, filename).resolve()
                if candidate.suffix.lower() in SQLITE_EXTENSIONS and candidate.is_file():
                    discovered.append(candidate)
                    if len(configured) + len(discovered) >= MAX_DISCOVERED_DATABASES:
                        break
            if len(configured) + len(discovered) >= MAX_DISCOVERED_DATABASES:
                break
        seen: set[Path] = set()
        result: list[Path] = []
        for path in (*configured, *discovered):
            if path not in seen:
                seen.add(path)
                result.append(path)
        return tuple(result)

    def _render_schema(self, databases: tuple[DatabaseTarget, ...], *, assistant_name: str) -> MessagePayload:
        lines = [f"<b>{escape(assistant_name)} membaca database bisnis secara read-only.</b>", ""]
        for target in databases:
            try:
                tables = _read_schema(target)
            except BusinessDatabaseError as exc:
                lines.append(f"<code>{escape(target.label)}</code>: gagal dibaca ({escape(str(exc))})")
                continue
            lines.append(f"Database: <code>{escape(target.label)}</code>")
            if not tables:
                lines.append("- Tidak ada tabel user-defined.")
                lines.append("")
                continue
            for table_name, columns in tables:
                column_text = ", ".join(
                    f"{name} {type_name}".strip()
                    for name, type_name in columns[:10]
                )
                if len(columns) > 10:
                    column_text += f", +{len(columns) - 10} kolom"
                lines.append(f"- <code>{escape(table_name)}</code>: {escape(column_text or '-')}")
            lines.append("")
        lines.append("Query SQL read-only bisa dikirim dengan format: <code>select ...</code>")
        return MessagePayload(text="\n".join(lines).strip(), parse_mode="HTML")

    def _run_sql(self, target: DatabaseTarget, sql: str, *, assistant_name: str) -> MessagePayload:
        normalized_sql = sql.strip()
        if not _is_readonly_sql(normalized_sql, target.kind):
            return format_error_payload(
                "Query database bisnis hanya boleh SELECT/WITH. PRAGMA schema hanya tersedia untuk SQLite.",
                assistant_name=assistant_name,
            )
        try:
            columns, rows = _run_readonly_query(target, normalized_sql)
        except BusinessDatabaseError as exc:
            return format_error_payload(
                f"Query gagal dijalankan secara read-only: {exc}",
                assistant_name=assistant_name,
            )

        lines = [
            f"<b>{escape(assistant_name)} menjalankan query database bisnis.</b>",
            "",
            f"Database: <code>{escape(target.label)}</code>",
            f"SQL: <code>{escape(normalized_sql)}</code>",
            "",
        ]
        if not columns:
            lines.append("Query selesai tanpa hasil tabular.")
            return MessagePayload(text="\n".join(lines), parse_mode="HTML")
        visible_rows = rows[:MAX_SQL_ROWS]
        if not visible_rows:
            lines.append("Tidak ada baris hasil.")
            return MessagePayload(text="\n".join(lines), parse_mode="HTML")
        lines.extend(_format_rows(columns, visible_rows))
        if len(rows) > MAX_SQL_ROWS:
            lines.append(f"... hasil dipotong ke {MAX_SQL_ROWS} baris pertama.")
        return MessagePayload(text="\n".join(lines), parse_mode="HTML")

    def _build_no_database_message(self, engine_hint: str | None) -> str:
        if engine_hint == "postgresql":
            return "Belum ada PostgreSQL URL di BUSINESS_DATABASE_URLS untuk project bisnis aktif."
        if engine_hint == "mysql":
            return "Belum ada MySQL URL di BUSINESS_DATABASE_URLS untuk project bisnis aktif."
        return (
            "Belum menemukan target database bisnis. Untuk SQLite, taruh file .db/.sqlite/.sqlite3 "
            "di project aktif atau set BUSINESS_DATABASE_PATHS. Untuk PostgreSQL/MySQL, set BUSINESS_DATABASE_URLS."
        )

    def _render_logic_summary(self, repo_root: Path, *, assistant_name: str) -> MessagePayload:
        summaries = _scan_logic_files(repo_root)
        if not summaries:
            return format_error_payload(
                "Belum menemukan file yang tampak seperti logika bisnis di project aktif.",
                assistant_name=assistant_name,
            )

        lines = [
            f"<b>{escape(assistant_name)} membaca kandidat logika bisnis project ini.</b>",
            "",
            f"Project: <code>{escape(str(repo_root))}</code>",
            "",
        ]
        for item in summaries[:MAX_LOGIC_FILES]:
            rel_path = item.path.relative_to(repo_root)
            symbol_text = ", ".join(item.symbols[:5]) or "-"
            lines.append(
                f"- <code>{escape(str(rel_path))}</code> "
                f"({item.line_count} baris, skor {item.score})"
            )
            lines.append(f"  Simbol: {escape(symbol_text)}")
        lines.append("")
        lines.append("Gunakan prompt spesifik seperti <code>baca logika bisnis file services/order.py</code> untuk analisis lanjutan via role read-only.")
        return MessagePayload(text="\n".join(lines), parse_mode="HTML")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _extract_sql(text: str) -> str | None:
    stripped = text.strip()
    lowered = stripped.lower()
    for prefix in ("sql:", "query:"):
        if lowered.startswith(prefix):
            return stripped[len(prefix):].strip()
    if SELECT_SQL.match(stripped) or PRAGMA_SQL.match(stripped):
        return stripped
    return None


def _extract_engine_hint(normalized_text: str) -> str | None:
    if "postgresql" in normalized_text or "postgres" in normalized_text:
        return "postgresql"
    if "mysql" in normalized_text:
        return "mysql"
    if "sqlite" in normalized_text:
        return "sqlite"
    return None


def _is_readonly_sql(sql: str, target_kind: str) -> bool:
    if ";" in sql.rstrip(";"):
        return False
    if FORBIDDEN_SQL.search(sql):
        return False
    if target_kind == "sqlite" and PRAGMA_SQL.match(sql):
        return True
    return bool(SELECT_SQL.match(sql))


class BusinessDatabaseError(RuntimeError):
    """Raised when a read-only database operation fails."""


def _database_target_from_url(url: str) -> DatabaseTarget | None:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme in {"postgres", "postgresql"}:
        return DatabaseTarget(kind="postgresql", label=_safe_database_label(url), url=url)
    if scheme in {"mysql", "mysql+pymysql"}:
        return DatabaseTarget(kind="mysql", label=_safe_database_label(url), url=url)
    if scheme in {"sqlite", "sqlite3"}:
        path = Path(parsed.path).expanduser().resolve()
        return DatabaseTarget(kind="sqlite", label=str(path), path=path)
    return None


def _target_matches_hint(target: DatabaseTarget, engine_hint: str | None) -> bool:
    return engine_hint is None or target.kind == engine_hint


def _safe_database_label(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = f":{parsed.port}" if parsed.port else ""
    database = parsed.path.lstrip("/") or "-"
    return f"{parsed.scheme}://{host}{port}/{database}"


def _read_schema(target: DatabaseTarget) -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    if target.kind == "sqlite" and target.path is not None:
        try:
            return _read_sqlite_schema(target.path)
        except sqlite3.Error as exc:
            raise BusinessDatabaseError(str(exc)) from exc
    if target.kind == "postgresql":
        return _read_postgresql_schema(target)
    if target.kind == "mysql":
        return _read_mysql_schema(target)
    raise BusinessDatabaseError(f"Target database tidak didukung: {target.kind}")


def _run_readonly_query(target: DatabaseTarget, sql: str) -> tuple[list[str], list[dict[str, object]]]:
    if target.kind == "sqlite" and target.path is not None:
        try:
            with _connect_readonly(target.path) as conn:
                conn.set_authorizer(_readonly_authorizer)
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(sql)
                rows = cursor.fetchmany(MAX_SQL_ROWS + 1)
                columns = [description[0] for description in cursor.description or []]
                return columns, [{column: row[column] for column in columns} for row in rows]
        except sqlite3.Error as exc:
            raise BusinessDatabaseError(str(exc)) from exc
    if target.kind == "postgresql":
        return _run_postgresql_query(target, sql)
    if target.kind == "mysql":
        return _run_mysql_query(target, sql)
    raise BusinessDatabaseError(f"Target database tidak didukung: {target.kind}")


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{quote(str(db_path), safe='/')}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _readonly_authorizer(action, arg1, arg2, db_name, trigger_name) -> int:
    denied = {
        sqlite3.SQLITE_ALTER_TABLE,
        sqlite3.SQLITE_ATTACH,
        sqlite3.SQLITE_CREATE_INDEX,
        sqlite3.SQLITE_CREATE_TABLE,
        sqlite3.SQLITE_CREATE_TEMP_INDEX,
        sqlite3.SQLITE_CREATE_TEMP_TABLE,
        sqlite3.SQLITE_CREATE_TEMP_TRIGGER,
        sqlite3.SQLITE_CREATE_TEMP_VIEW,
        sqlite3.SQLITE_CREATE_TRIGGER,
        sqlite3.SQLITE_CREATE_VIEW,
        sqlite3.SQLITE_DELETE,
        sqlite3.SQLITE_DETACH,
        sqlite3.SQLITE_DROP_INDEX,
        sqlite3.SQLITE_DROP_TABLE,
        sqlite3.SQLITE_DROP_TEMP_INDEX,
        sqlite3.SQLITE_DROP_TEMP_TABLE,
        sqlite3.SQLITE_DROP_TEMP_TRIGGER,
        sqlite3.SQLITE_DROP_TEMP_VIEW,
        sqlite3.SQLITE_DROP_TRIGGER,
        sqlite3.SQLITE_DROP_VIEW,
        sqlite3.SQLITE_INSERT,
        sqlite3.SQLITE_PRAGMA,
        sqlite3.SQLITE_REINDEX,
        sqlite3.SQLITE_TRANSACTION,
        sqlite3.SQLITE_UPDATE,
    }
    if action == sqlite3.SQLITE_PRAGMA and (arg1 or "").lower() in {"table_info", "table_xinfo", "index_list", "foreign_key_list"}:
        return sqlite3.SQLITE_OK
    if action in denied:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _read_sqlite_schema(db_path: Path) -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    with _connect_readonly(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        result: list[tuple[str, tuple[tuple[str, str], ...]]] = []
        for (table_name,) in rows:
            columns = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
            result.append(
                (
                    table_name,
                    tuple((column[1], column[2]) for column in columns),
                )
            )
        return tuple(result)


def _read_postgresql_schema(target: DatabaseTarget) -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    sql = (
        "SELECT table_schema, table_name, column_name, data_type "
        "FROM information_schema.columns "
        "WHERE table_schema NOT IN ('pg_catalog', 'information_schema') "
        "ORDER BY table_schema, table_name, ordinal_position"
    )
    columns, rows = _run_postgresql_query(target, sql, max_rows=MAX_SCHEMA_COLUMNS)
    return _group_schema_rows(rows)


def _read_mysql_schema(target: DatabaseTarget) -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    sql = (
        "SELECT table_schema, table_name, column_name, data_type "
        "FROM information_schema.columns "
        "WHERE table_schema = DATABASE() "
        "ORDER BY table_schema, table_name, ordinal_position"
    )
    columns, rows = _run_mysql_query(target, sql, max_rows=MAX_SCHEMA_COLUMNS)
    return _group_schema_rows(rows)


def _group_schema_rows(rows: list[dict[str, object]]) -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    grouped: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        schema = str(row.get("table_schema") or "")
        table = str(row.get("table_name") or "")
        column = str(row.get("column_name") or "")
        data_type = str(row.get("data_type") or "")
        key = f"{schema}.{table}" if schema else table
        grouped.setdefault(key, []).append((column, data_type))
    return tuple((table_name, tuple(columns)) for table_name, columns in grouped.items())


def _run_postgresql_query(
    target: DatabaseTarget,
    sql: str,
    *,
    max_rows: int = MAX_SQL_ROWS + 1,
) -> tuple[list[str], list[dict[str, object]]]:
    if not target.url:
        raise BusinessDatabaseError("URL PostgreSQL belum dikonfigurasi.")
    try:
        import psycopg
    except ImportError as exc:
        raise BusinessDatabaseError(
            "Driver PostgreSQL belum terpasang. Install dependency 'psycopg[binary]'."
        ) from exc
    try:
        with psycopg.connect(target.url, autocommit=True) as conn:
            conn.execute("SET default_transaction_read_only = on")
            with conn.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchmany(max_rows)
                columns = [description.name for description in cursor.description or []]
                return columns, [
                    {column: row[index] for index, column in enumerate(columns)}
                    for row in rows
                ]
    except Exception as exc:
        raise BusinessDatabaseError(str(exc)) from exc


def _run_mysql_query(
    target: DatabaseTarget,
    sql: str,
    *,
    max_rows: int = MAX_SQL_ROWS + 1,
) -> tuple[list[str], list[dict[str, object]]]:
    if not target.url:
        raise BusinessDatabaseError("URL MySQL belum dikonfigurasi.")
    try:
        import pymysql
    except ImportError as exc:
        raise BusinessDatabaseError(
            "Driver MySQL belum terpasang. Install dependency 'PyMySQL'."
        ) from exc
    parsed = urlparse(target.url)
    try:
        conn = pymysql.connect(
            host=parsed.hostname or "localhost",
            port=parsed.port or 3306,
            user=unquote(parsed.username or ""),
            password=unquote(parsed.password or ""),
            database=parsed.path.lstrip("/") or None,
            charset="utf8mb4",
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            with conn.cursor() as cursor:
                cursor.execute("SET SESSION TRANSACTION READ ONLY")
                cursor.execute(sql)
                rows = list(cursor.fetchmany(max_rows))
                columns = [description[0] for description in cursor.description or []]
                return columns, rows
        finally:
            conn.close()
    except Exception as exc:
        raise BusinessDatabaseError(str(exc)) from exc


def _format_rows(columns: list[str], rows: list[dict[str, object]]) -> list[str]:
    lines = [f"Hasil: {len(rows)} baris", ""]
    for row_index, row in enumerate(rows, start=1):
        values = []
        for column in columns[:8]:
            value = _shorten_cell(row.get(column))
            values.append(f"{column}={value}")
        if len(columns) > 8:
            values.append(f"+{len(columns) - 8} kolom")
        lines.append(f"{row_index}. <code>{escape(' | '.join(values))}</code>")
    return lines


def _shorten_cell(value) -> str:
    if value is None:
        return "NULL"
    text = str(value).replace("\n", " ")
    if len(text) > MAX_CELL_LENGTH:
        return text[: MAX_CELL_LENGTH - 1] + "..."
    return text


def _scan_logic_files(repo_root: Path) -> tuple[LogicFileSummary, ...]:
    summaries: list[LogicFileSummary] = []
    scanned = 0
    for dirpath, dirnames, filenames in os.walk(repo_root, topdown=True):
        dirnames[:] = [dirname for dirname in dirnames if dirname not in SKIP_DIR_NAMES]
        dirnames.sort()
        for filename in sorted(filenames):
            if scanned >= MAX_SCAN_FILES:
                break
            path = Path(dirpath, filename).resolve()
            if path.suffix.lower() not in LOGIC_EXTENSIONS:
                continue
            scanned += 1
            summary = _summarize_logic_file(repo_root, path)
            if summary is not None:
                summaries.append(summary)
        if scanned >= MAX_SCAN_FILES:
            break
    summaries.sort(key=lambda item: (item.score, len(item.symbols), str(item.path)), reverse=True)
    return tuple(summaries[:MAX_LOGIC_FILES])


def _summarize_logic_file(repo_root: Path, path: Path) -> LogicFileSummary | None:
    try:
        if path.stat().st_size > MAX_SCAN_BYTES:
            return None
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    rel_text = str(path.relative_to(repo_root)).lower()
    score = 0
    for marker in LOGIC_FILE_MARKERS:
        if marker in rel_text:
            score += 5
        if marker in text.lower():
            score += 1
    symbols = tuple(_extract_symbols(text))
    score += min(len(symbols), 8)
    if score < 5:
        return None
    return LogicFileSummary(
        path=path,
        score=score,
        line_count=text.count("\n") + 1 if text else 0,
        symbols=symbols,
    )


def _extract_symbols(text: str) -> list[str]:
    patterns = (
        re.compile(r"^\s*(?:async\s+def|def)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.MULTILINE),
        re.compile(r"^\s*class\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.MULTILINE),
        re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.MULTILINE),
        re.compile(r"^\s*(?:export\s+)?(?:const|let)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=", re.MULTILINE),
    )
    found: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            name = match.group(1)
            if name not in found:
                found.append(name)
            if len(found) >= 8:
                return found
    return found


def _is_within(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    return resolved == root or root in resolved.parents
