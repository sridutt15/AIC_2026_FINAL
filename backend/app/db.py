"""Postgres (Supabase) database layer via SQLAlchemy (Phase 12).

`engine` (pool_pre_ping=True) and `SessionLocal` are the canonical access
points bound to DATABASE_URL. The Phase 1-11 modules keep their existing
sqlite3-shaped call pattern: get_connection() returns a thin facade over a
SQLAlchemy connection that accepts the same calls (positional ? placeholders,
row["col"] access, fetchone/fetchall, commit/close) while executing against
Postgres. The facade translates the SQLite-only constructs it receives
(INSERT OR REPLACE, `IS ?`) into their Postgres equivalents and routes every
statement to the active schema — `public` for the app, or a per-test schema
under pytest (see tests/conftest.py). SET LOCAL (transaction-scoped) is used
for schema routing because session-level SET is unreliable through the
Supabase transaction pooler (port 6543).
"""

import json
import re
import threading

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.tables import Base

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# Schema currently targeted by all statements. "public" for the running app;
# tests point it at an isolated per-test schema (tests/conftest.py). Pytest
# runs tests sequentially and TestClient worker threads read this at call
# time, so plain module state is sufficient.
_active_schema = "public"

# Schemas whose tables/personas this process has already initialized.
# init_db() must be cheap when called repeatedly (the Phase 11 timed_stage
# decorator calls it before every wrapped stage), and each create_all()
# round trip costs ~50ms against the cloud database.
_initialized_schemas: set[str] = set()
_init_lock = threading.Lock()

# Primary keys per table, from the model metadata — used to translate
# SQLite's INSERT OR REPLACE into a Postgres upsert.
_TABLE_PKS: dict[str, tuple[str, ...]] = {
    table.name: tuple(column.name for column in table.primary_key.columns)
    for table in Base.metadata.sorted_tables
}

# Seeded personas (Phase 8): role-based access rules applied by
# core/persona/access_control.filter_for_persona before any response leaves
# the API layer. Rules are generic — column ROLE tags, never specific names.
#   allowed_domains  : dimension domains the persona may see (None = all)
#   restricted_roles : contract column roles hidden from this persona
#   restricted_columns: exact column names hidden from this persona
#   max_slices       : per-dimension slice-detail cap (None = unlimited)
_SEED_PERSONAS = [
    {
        "persona_id": "category_manager",
        "name": "Category Manager",
        "access_json": {
            "description": "Tactical, broad access: every domain, full slice detail.",
            "allowed_domains": None,
            "restricted_roles": [],
            "restricted_columns": [],
            "max_slices": None,
        },
    },
    {
        "persona_id": "cfo",
        "name": "CFO",
        "access_json": {
            "description": (
                "Headline financial view: cost-breakdown and operational-detail "
                "measures hidden, identifier roles restricted, slice detail capped."
            ),
            "allowed_domains": None,
            "restricted_roles": ["identifier"],
            "restricted_columns": [
                "delivery_fee",
                "platform_fee",
                "estimated_delivery_minutes",
                "actual_delivery_minutes",
            ],
            "max_slices": 5,
        },
    },
]


def use_schema(schema: str) -> None:
    """Point every subsequent statement at `schema` (test isolation)."""
    global _active_schema
    _active_schema = schema


# INSERT OR REPLACE INTO t (cols) VALUES (placeholders) — the exact shape
# every INSERT OR REPLACE statement in the app uses.
_INSERT_OR_REPLACE_RE = re.compile(
    r"INSERT OR REPLACE INTO (\w+)\s*\(([^)]*)\)\s*VALUES\s*\(([^)]*)\)",
    re.IGNORECASE,
)


def _upsert_from_sqlite(match: re.Match) -> str:
    """One INSERT OR REPLACE statement -> Postgres upsert (or plain INSERT
    for tables without a primary key — SQLite's REPLACE behaves as a plain
    INSERT for those too). ON CONFLICT follows the VALUES clause."""
    table = match.group(1)
    columns = [column.strip() for column in match.group(2).split(",")]
    values = match.group(3)
    pk = _TABLE_PKS.get(table, ())
    if not pk:
        return f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({values})"
    assignments = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c not in pk)
    return (
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({values}) "
        f"ON CONFLICT ({', '.join(pk)}) DO UPDATE SET {assignments}"
    )


def _translate_sql(sql: str) -> str:
    """Translate the SQLite-dialect SQL the app emits into Postgres SQL.

    1. INSERT OR REPLACE INTO t (cols) VALUES (...) -> Postgres upsert
       (PK-less tables keep a plain INSERT, matching SQLite behaviour).
    2. `col IS ?` -> `col IS NOT DISTINCT FROM ?` — SQLite's IS compares
       values NULL-safely; Postgres's IS does not.
    3. Positional ? -> named SQLAlchemy binds :p0, :p1, ... in order.
    """
    sql = _INSERT_OR_REPLACE_RE.sub(_upsert_from_sqlite, sql)
    sql = re.sub(r"(\w+)\s+IS\s+\?", r"\1 IS NOT DISTINCT FROM ?", sql, flags=re.IGNORECASE)
    bind_names = iter(range(sql.count("?")))
    return re.sub(r"\?", lambda _: f":p{next(bind_names)}", sql)


class CompatRow(tuple):
    """sqlite3.Row-shaped result row: value iteration + tuple equality +
    string-key access, so `row["col"]`, `dict(row)`, and `row == (a, b)` all
    behave exactly as they did against SQLite."""

    def __new__(cls, values, keys):
        row = super().__new__(cls, values)
        row._keys = tuple(keys)
        return row

    def keys(self) -> list:
        return list(self._keys)

    def __getitem__(self, key):
        if isinstance(key, str):
            return tuple.__getitem__(self, self._keys.index(key))
        return tuple.__getitem__(self, key)


class CompatCursor:
    """fetchone/fetchall over a SQLAlchemy result, returning CompatRows.

    Statements that return no rows (INSERT/UPDATE/DELETE) have their result
    auto-closed by SQLAlchemy, so keys() may be unavailable — recorded as an
    empty key list; fetches are never meaningfully called on those statements.
    """

    def __init__(self, result, keys):
        self._result = result
        self._keys = list(keys)

    def _row(self, row) -> CompatRow:
        return CompatRow(tuple(row), self._keys)

    def fetchone(self):
        row = self._result.fetchone()
        return None if row is None else self._row(row)

    def fetchall(self) -> list:
        return [self._row(row) for row in self._result.fetchall()]


class CompatConnection:
    """sqlite3-shaped facade over a SQLAlchemy Connection.

    All statements execute inside the connection's current transaction;
    `SET LOCAL search_path` (re-applied at the start of each transaction)
    routes unqualified table names to the active schema.
    """

    def __init__(self, sa_conn, schema: str):
        self._conn = sa_conn
        self._schema = schema
        self._search_path_set = False

    def _ensure_search_path(self) -> None:
        if not self._search_path_set:
            self._conn.exec_driver_sql(f'SET LOCAL search_path TO "{self._schema}"')
            self._search_path_set = True

    def execute(self, sql: str, params=()) -> CompatCursor:
        translated = _translate_sql(sql)
        self._ensure_search_path()
        if params:
            bind = {f"p{i}": value for i, value in enumerate(params)}
            result = self._conn.execute(text(translated), bind)
        else:
            result = self._conn.execute(text(translated))
        try:
            keys = list(result.keys())
        except Exception:  # no-rows statements auto-close their result
            keys = []
        return CompatCursor(result, keys)

    def commit(self) -> None:
        if self._conn.in_transaction():
            self._conn.commit()
        self._search_path_set = False

    def rollback(self) -> None:
        if self._conn.in_transaction():
            self._conn.rollback()
        self._search_path_set = False

    def close(self) -> None:
        self._conn.close()


def get_connection() -> CompatConnection:
    """Open a SQLAlchemy-backed connection speaking the sqlite3 call shape."""
    return CompatConnection(engine.connect(), _active_schema)


def init_db() -> None:
    """Create every table in the active schema and seed personas if empty.

    One transaction: CREATE SCHEMA IF NOT EXISTS, SET LOCAL search_path,
    Base.metadata.create_all (idempotent), persona seeding. Runs once per
    (process, schema) — repeated calls (e.g. from timed_stage or the TestClient
    lifespan) are a no-op once the schema is initialized.
    """
    schema = _active_schema
    with _init_lock:
        if schema in _initialized_schemas:
            return
        conn = engine.connect()
        try:
            conn.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            conn.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
            Base.metadata.create_all(bind=conn)
            count = conn.execute(text("SELECT COUNT(*) AS n FROM personas")).scalar()
            if not count:
                for persona in _SEED_PERSONAS:
                    conn.execute(
                        text(
                            "INSERT INTO personas (persona_id, name, access_json) "
                            "VALUES (:persona_id, :name, :access_json)"
                        ),
                        {
                            "persona_id": persona["persona_id"],
                            "name": persona["name"],
                            "access_json": json.dumps(persona["access_json"]),
                        },
                    )
            conn.commit()
        finally:
            conn.close()
        _initialized_schemas.add(schema)
