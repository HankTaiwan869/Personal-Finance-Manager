from itertools import pairwise
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QPushButton,
    QSpinBox,
)
from pytestqt.exceptions import TimeoutError

from financial_hub.models import Portfolio
from financial_hub.ui.main_window import MainWindow


def _projection_button(window: MainWindow) -> QPushButton:
    buttons = [
        button
        for button in window.dashboard.findChildren(QPushButton)
        if button.text() == "View Projection"
    ]
    assert len(buttons) == 1
    return buttons[0]


def _projection_dialog(window: MainWindow) -> QDialog:
    # Keep this compatible with either public naming convention while the
    # dialog is being moved out of the stacked page layout.
    dialog = getattr(window, "projection_dialog", None)
    if dialog is None:
        dialog = getattr(window, "projection", None)
    assert isinstance(dialog, QDialog)
    return dialog


def _projection_years(dialog: QDialog) -> QSpinBox:
    years = getattr(dialog, "years", None)
    if years is None:
        years = dialog.findChild(QSpinBox)
    assert isinstance(years, QSpinBox)
    return years


def _projection_rates(dialog: QDialog) -> list[QDoubleSpinBox]:
    rates = getattr(dialog, "rates", None)
    if rates is None:
        rates = dialog.findChildren(QDoubleSpinBox)
    rates = list(rates)
    assert len(rates) == 3
    assert all(isinstance(rate, QDoubleSpinBox) for rate in rates)
    return rates


def _projection_portfolio(dialog: QDialog) -> QComboBox:
    portfolio = getattr(dialog, "portfolio", None)
    if portfolio is None:
        combos = dialog.findChildren(QComboBox)
        assert len(combos) == 1
        portfolio = combos[0]
    assert isinstance(portfolio, QComboBox)
    return portfolio


def _projection_chart(dialog: QDialog) -> QWebEngineView | None:
    chart = getattr(dialog, "chart", None)
    if chart is not None:
        assert isinstance(chart, QWebEngineView)
        return chart
    return dialog.findChild(QWebEngineView)


def _wait_for_plotly(qtbot, chart: QWebEngineView) -> None:
    rendered: list[bool] = []
    active = True
    timer = QTimer()
    timer.setSingleShot(True)
    timer.setInterval(50)
    script = (
        "typeof Plotly !== 'undefined' && "
        "document.querySelector('.plotly-graph-div') !== null"
    )

    def check_rendered() -> None:
        if not active:
            return

        def checked(value: object) -> None:
            if not active:
                return
            if value:
                rendered.append(True)
            else:
                timer.start()

        chart.page().runJavaScript(script, checked)

    timer.timeout.connect(check_rendered)
    try:
        check_rendered()
        qtbot.waitUntil(lambda: bool(rendered), timeout=5000)
    finally:
        active = False
        timer.stop()


@pytest.mark.parametrize("callback_pending", [False, True])
def test_plotly_polling_stops_after_timeout(qtbot, monkeypatch, callback_pending):
    chart = Mock(spec=QWebEngineView)
    callbacks = []

    def run_javascript(script, callback):
        callbacks.append(callback)
        if not callback_pending:
            callback(False)

    chart.page.return_value.runJavaScript.side_effect = run_javascript
    wait_until = qtbot.waitUntil
    monkeypatch.setattr(
        qtbot, "waitUntil", lambda callback, **kwargs: wait_until(callback, timeout=10)
    )

    with pytest.raises(TimeoutError):
        _wait_for_plotly(qtbot, chart)

    # Simulate teardown, including a JavaScript result arriving after timeout.
    chart.page.side_effect = RuntimeError("chart has been deleted")
    if callback_pending:
        callbacks[0](False)
    qtbot.wait(100)
    chart.page.assert_called_once()


def _open_projection(qtbot, window: MainWindow) -> QDialog:
    # There must not be a web-engine chart merely because the main window was
    # constructed. It is loaded on demand from this button.
    assert not window.findChildren(QWebEngineView)
    _projection_button(window).click()
    dialog = _projection_dialog(window)
    qtbot.waitUntil(dialog.isVisible, timeout=2000)
    qtbot.waitUntil(lambda: _projection_chart(dialog) is not None, timeout=5000)
    chart = _projection_chart(dialog)
    assert chart is not None
    _wait_for_plotly(qtbot, chart)
    return dialog


def test_projection_button_opens_resizable_dialog_with_defaults(qtbot, db):
    _engine, factory, _ids = db
    window = MainWindow(factory)
    qtbot.addWidget(window)
    window.show()

    assert "Projection" not in window.PAGE_NAMES
    assert all(button.text() != "Projection" for button in window.nav_buttons)
    assert _projection_button(window).isEnabled()

    dialog = _open_projection(qtbot, window)
    assert dialog.isVisible()
    assert dialog.minimumWidth() < dialog.maximumWidth()
    assert dialog.minimumHeight() < dialog.maximumHeight()

    years = _projection_years(dialog)
    assert years.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons
    rates = _projection_rates(dialog)
    assert all(
        control.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons
        for control in rates
    )
    assert years.value() == 30
    assert [rate.value() for rate in rates] == [6.5, 9.0, 11.5]
    assert years.minimum() == 0
    assert years.maximum() == 100
    assert not years.keyboardTracking()

    years.setFocus()
    years.lineEdit().selectAll()
    qtbot.keyClicks(years, "0")
    qtbot.keyPress(years, Qt.Key.Key_Return)
    assert years.value() == 0

    years.lineEdit().selectAll()
    qtbot.keyClicks(years, "30")
    qtbot.keyPress(years, Qt.Key.Key_Return)
    assert years.value() == 30

    years.stepUp()
    assert years.value() == 31


def test_projection_uses_dashboard_portfolio_and_persists_settings(qtbot, db):
    _engine, factory, (core_id, _security_id) = db
    window = MainWindow(factory)
    qtbot.addWidget(window)
    window.show()

    dashboard_portfolio = window.dashboard.portfolio
    dashboard_index = dashboard_portfolio.findData(core_id)
    assert dashboard_index >= 0
    dashboard_portfolio.setCurrentIndex(dashboard_index)
    assert dashboard_portfolio.currentData() == core_id

    dialog = _open_projection(qtbot, window)
    projection_portfolio = _projection_portfolio(dialog)
    assert projection_portfolio.currentData() == core_id
    assert projection_portfolio.currentText() == "Core"

    years = _projection_years(dialog)
    rates = _projection_rates(dialog)
    years.setValue(42)
    for control, value in zip(rates, (4.25, 8.75, 13.0), strict=True):
        control.setValue(value)

    dialog.close()
    qtbot.waitUntil(lambda: not dialog.isVisible(), timeout=2000)
    _projection_button(window).click()
    qtbot.waitUntil(dialog.isVisible, timeout=2000)

    assert _projection_years(dialog).value() == 42
    assert [rate.value() for rate in _projection_rates(dialog)] == [
        4.25,
        8.75,
        13.0,
    ]
    assert _projection_portfolio(dialog).currentData() == core_id


def test_projection_portfolio_selector_still_tracks_available_portfolios(qtbot, db):
    _engine, factory, _ids = db
    with factory.begin() as session:
        session.add(Portfolio(name="Growth"))

    window = MainWindow(factory)
    qtbot.addWidget(window)
    dialog = _open_projection(qtbot, window)

    assert [
        _projection_portfolio(dialog).itemText(index)
        for index in range(_projection_portfolio(dialog).count())
    ] == ["All portfolios", "Core", "Growth"]


def test_accounting_details_form_has_room_between_rows(qtbot, db):
    _engine, factory, _ids = db
    window = MainWindow(factory)
    qtbot.addWidget(window)
    window.show_page(window.PAGE_NAMES.index("Transactions"))
    window.resize(900, 620)
    window.show()
    qtbot.waitExposed(window)

    accounting = next(
        group
        for group in window.transactions.findChildren(QGroupBox)
        if group.title() == "Accounting details"
    )
    form = accounting.layout()
    assert isinstance(form, QFormLayout)
    assert form.verticalSpacing() == 14
    assert form.horizontalSpacing() == 24
    assert form.contentsMargins().top() == 30

    fields = (
        window.transactions.shares,
        window.transactions.amount,
    )
    assert all(field.height() >= 42 for field in fields)
    gaps = [
        lower.geometry().top() - upper.geometry().bottom() - 1
        for upper, lower in pairwise(fields)
    ]
    assert min(gaps) >= 14