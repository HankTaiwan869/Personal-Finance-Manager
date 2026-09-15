# Financial Hub

[![CI](https://github.com/HankTaiwan869/Personal-Finance-Manager/actions/workflows/ci.yml/badge.svg)](https://github.com/HankTaiwan869/Personal-Finance-Manager/actions/workflows/ci.yml)

Financial Hub is a local PyQt desktop application for tracking personal finances and portfolios. It combines portfolio activity, investment returns, projections, monthly cash flow, and annual net-worth in a local SQLite database.

I built it to replace my own spreadsheet-based workflow. Its scope is intentionally personal.

## Screenshots

The main application views are shown below.

| Dashboard | Personal Finance | Projection |
| --- | --- | --- |
| ![Portfolio dashboard](docs/screenshots/dashboard.png) | ![Monthly and yearly personal-finance records](docs/screenshots/personal-finance.png) | ![Compound-growth projection](docs/screenshots/projection.png) |

## Key features

- Manage multiple portfolios and track buys, sells, dividends, and opening positions.
- Calculate market value, profit, dividend income, annual/monthly IRR.
- Visualize future portfolio projections with adjustable expected returns.
- Search, sort, edit, and delete transaction history.
- Record monthly income, spending, annual asset, investment, debt, and net-worth.
- Back up the live SQLite database and import from Excel or SQLite cash-flow records.


## Architecture

```text
PyQt views and dialogs
        |
        v
Application services  <---->  Provider interface  <---->  FinMind API
        |
        v
SQLAlchemy models
        |
        v
Local SQLite database
```

```text
financial_hub/
|-- ui/             # Main window, feature views, dialogs, table models, workers
|-- services/       # Transactions, analytics, quotes, personal-finance rules
|-- providers/      # Provider contract and FinMind HTTP implementation
|-- models.py       # SQLAlchemy entities and database constraints
|-- database.py     # Engine setup, schema checks, sessions, and backup
`-- data_import.py  # Legacy cash-flow import pipeline

scripts/            # One-time Personal Finance migration/import helpers
tests/              # Service, persistence, provider, and GUI regression tests
```

## Tech stack

| Area | Technology |
| --- | --- |
| Language and packaging | Python 3.11+, `uv` |
| Desktop UI | PyQt6, Qt WebEngine |
| Persistence | SQLite, SQLAlchemy 2 |
| Market data | HTTPX, FinMind API |
| Analytics and charts | `pyxirr`, `Decimal`, Plotly |
| Credentials | `keyring` |
| Testing and CI | pytest, pytest-qt, Ruff, GitHub Actions |

## Install and run

The project is developed primarily for Windows.

```powershell
git clone https://github.com/HankTaiwan869/Personal-Finance-Manager.git
cd Personal-Finance-Manager
uv sync --dev
uv run financial-hub
```

`run.bat` is also available as a Windows launcher.

On first launch, save a FinMind token under **Settings**. The token is stored through `keyring`.

Application data is stored in the operating system's standard per-user data directory, such as:

```text
Windows: %LOCALAPPDATA%\IRRCalculator\financial-hub.sqlite3
Linux: ~/.local/share/IRRCalculator/financial-hub.sqlite3
```

## Testing

```powershell
uv run ruff check .
uv run pytest
```

The test suite uses temporary SQLite databases, mocked HTTP transports/providers, and `pytest-qt`:

- transaction signs, validation, backdated edits, and non-negative holdings;
- ledger replay, decimal valuation, dividends, XIRR edge cases, and projection math;
- quote updates, retry behavior, provider errors, database constraints, backup, and import/migration paths;
- PyQt navigation, form behavior, view coordination, sorting, styling, lazy chart loading, and background work.


## Scope and limitations

The Personal Finance page is a deliberately small companion to the investment tracker, not a complete budgeting or accounting system. The projection is a compound-growth scenario, not a forecast, and the application is not financial advice.

AI coding agents are one part of my development workflow. I remain responsible for reviewing, understanding, testing, debugging, and maintaining the code.
