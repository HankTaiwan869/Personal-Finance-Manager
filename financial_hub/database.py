from __future__ import annotations

import sqlite3
from pathlib import Path

from platformdirs import user_data_path
from sqlalchemy import Engine, create_engine, event, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, Portfolio

SCHEMA_VERSION = 1


def app_data_dir() -> Path:
    # Keep this directory stable so existing portfolios remain available when
    # the user-facing application name changes.
    return user_data_path("IRRCalculator", appauthor=False)


def default_database_path() -> Path:
    # v1 intentionally uses a new filename.  The previous application
    # database is left untouched and is never interpreted as this schema.
    return app_data_dir() / "financial-hub.sqlite3"


def create_database_engine(path: Path | str | None = None) -> Engine:
    database_path = Path(path) if path is not None else default_database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{database_path}", future=True)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def initialize_database(engine: Engine) -> bool:
    """Create or validate the deliberately single-version v1 schema.

    A database with no user tables and ``PRAGMA user_version = 0`` is a fresh
    database and is initialized in place. Any populated database that is not
    already the exact v1 shape is rejected. The one-time Personal Finance
    table addition is performed explicitly with
    ``python -m scripts.migrate_personal_finance``.

    Returns ``True`` when a new schema was created.  The return value lets the
    application run its one-time FinMind/legacy bootstrap without making
    isolated database tests perform network access.
    """
    current = _schema_user_version(engine)
    tables = set(inspect(engine).get_table_names())
    expected = set(Base.metadata.tables)

    if current == 0 and not tables:
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql(f"PRAGMA user_version = {SCHEMA_VERSION}")
        return True

    if current != SCHEMA_VERSION or tables != expected:
        if current == SCHEMA_VERSION and tables == {
            "portfolios",
            "securities",
            "transactions",
            "quotes",
        }:
            raise RuntimeError(
                "This v1 database is missing the Personal Finance tables. "
                "Run `python -m scripts.migrate_personal_finance` once, then "
                "restart the app."
            )
        actual = current if current else "0 (unversioned)"
        raise RuntimeError(
            f"Unsupported database schema {actual}; this app supports schema "
            f"{SCHEMA_VERSION} only. Create a new database."
        )
    return False


def _schema_user_version(engine: Engine) -> int:
    with engine.connect() as connection:
        value = connection.exec_driver_sql("PRAGMA user_version").scalar_one()
    return int(value)


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def ensure_default_portfolio(session: Session) -> int:
    portfolio_id = session.scalar(select(Portfolio.id).limit(1))
    if portfolio_id is not None:
        return portfolio_id
    portfolio = Portfolio(name="My Portfolio")
    session.add(portfolio)
    session.flush()
    return portfolio.id


def backup_database(engine: Engine, destination: Path | str) -> Path:
    target = Path(destination).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    source_path = Path(str(engine.url.database)).resolve()
    if target == source_path:
        raise ValueError("Choose a backup path different from the active database.")
    raw = engine.raw_connection()
    try:
        with sqlite3.connect(target) as output:
            raw.driver_connection.backup(output)
    finally:
        raw.close()
    return target
