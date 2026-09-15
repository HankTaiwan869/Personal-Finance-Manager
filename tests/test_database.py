import sqlite3
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from financial_hub import database
from financial_hub.database import (
    create_database_engine,
    initialize_database,
)
from financial_hub.models import Portfolio, Quote, Security


def test_app_data_dir_uses_platform_data_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(
        database,
        "user_data_path",
        lambda app_name, appauthor=None: tmp_path / app_name,
    )

    assert database.app_data_dir() == tmp_path / "IRRCalculator"


def test_foreign_keys_uniqueness_and_positive_quotes(db):
    _engine, factory, (_portfolio_id, security_id) = db
    with pytest.raises(IntegrityError), factory.begin() as session:
        session.add(Portfolio(name="Core"))
    with pytest.raises(IntegrityError), factory.begin() as session:
        session.add(Security(symbol="2330", name_zh="duplicate"))
    with pytest.raises(IntegrityError), factory.begin() as session:
        today = __import__("datetime").date.today()
        session.add(
            Quote(
                security_id=security_id,
                market_date=today,
                refresh_cycle_date=today,
                close=Decimal("0.00"),
            )
        )


def test_fresh_database_uses_simplified_v1_schema(tmp_path):
    path = tmp_path / "fresh.sqlite3"
    engine = create_database_engine(path)
    initialize_database(engine)

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (1,)
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {"portfolios", "securities", "transactions", "quotes"}.issubset(
            tables
        )
        assert {"schema_meta", "import_runs", "transaction_audit"}.isdisjoint(tables)

        transaction_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(transactions)")
        }
        assert {"shares_delta", "amount"}.issubset(transaction_columns)
        assert {"source_key", "deleted_at"}.isdisjoint(transaction_columns)

        quote_columns = {
            row[1]: row[2] for row in connection.execute("PRAGMA table_info(quotes)")
        }
        assert quote_columns["close"].upper().startswith("NUMERIC")

    # Re-opening an already-supported v1 database is a no-op.
    initialize_database(engine)
    engine.dispose()


def test_old_v1_shape_gets_personal_finance_migration_guidance(tmp_path):
    path = tmp_path / "old-v1.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE portfolios (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
            CREATE TABLE securities (id INTEGER PRIMARY KEY, symbol TEXT NOT NULL);
            CREATE TABLE transactions (id INTEGER PRIMARY KEY, portfolio_id INTEGER NOT NULL);
            CREATE TABLE quotes (id INTEGER PRIMARY KEY, security_id INTEGER NOT NULL);
            PRAGMA user_version = 1;
            """
        )

    engine = create_database_engine(path)
    with pytest.raises(RuntimeError, match=r"scripts\.migrate_personal_finance"):
        initialize_database(engine)
    engine.dispose()
