from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from sqlalchemy import select

from . import __version__
from .credentials import get_finmind_token
from .database import (
    create_database_engine,
    default_database_path,
    ensure_default_portfolio,
    initialize_database,
    session_factory,
)
from .models import Security
from .providers import FinMindProvider
from .services.quotes import sync_security_master
from .ui.main_window import MainWindow
from .ui.theme import stylesheet

APP_USER_MODEL_ID = f"IRRCalculator.Desktop.{__version__}"


def application_icon_path() -> Path:
    return Path(__file__).resolve().parent / "assets" / "investment.ico"


def bootstrap_new_database(factory) -> int:
    """Populate the FinMind security master for a new database."""
    try:
        token = get_finmind_token()
    except Exception:  # noqa: BLE001 - an unavailable credential backend is optional
        token = ""
    provider = FinMindProvider(token)

    with factory.begin() as session:
        return sync_security_master(session, provider)


def build_application(
    argv: list[str] | None = None, database_path=None
) -> tuple[QApplication, MainWindow]:
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                APP_USER_MODEL_ID
            )
        except (AttributeError, OSError):
            pass
    app = QApplication.instance() or QApplication(argv or sys.argv)
    app.setDesktopFileName("financial-hub")
    app.setApplicationName("Financial Hub")
    # Keep the organization name stable: changing it can change Qt's settings
    # namespace and break integrations that rely on the existing app identity.
    # Keep the database storage path stable as well; see database.app_data_dir().
    app.setOrganizationName("IRRCalculator")
    icon = QIcon(str(application_icon_path()))
    app.setWindowIcon(icon)
    app.setStyleSheet(stylesheet())
    requested_path = (
        Path(database_path) if database_path is not None else default_database_path()
    )
    engine = create_database_engine(requested_path)
    initialize_database(engine)
    factory = session_factory(engine)
    with factory.begin() as session:
        ensure_default_portfolio(session)
    # Explicit database paths are primarily used by tests and tooling.  The
    # bundled first-run bootstrap belongs to the application's fresh default
    # database only, so initialization itself never performs network access.
    needs_bootstrap = False
    if requested_path.resolve() == default_database_path().resolve():
        with factory() as session:
            needs_bootstrap = session.scalar(select(Security.id).limit(1)) is None
    window = MainWindow(
        factory,
        bootstrap=(lambda: bootstrap_new_database(factory))
        if needs_bootstrap
        else None,
    )
    window.setWindowIcon(icon)
    window._database_engine = engine  # retain engine for application lifetime
    app.aboutToQuit.connect(window.shutdown)
    return app, window


def main() -> int:
    app, window = build_application()
    window.show()
    return app.exec()
