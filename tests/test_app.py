from datetime import date, datetime, timezone
from pathlib import Path
import json

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import market_data
from market_data import DataDownloadError, StockHistory

APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def app(monkeypatch):
    data = {"AAPL": [100, 110, 99, 108.9, 119.79],
            "MSFT": [200, 202, 198, 205, 210],
            "NVDA": [50, 55, 52, 60, 70]}

    def history(symbol):
        series = pd.Series(data[symbol], index=pd.date_range("2026-10-12", periods=5, freq="B"),
                           name=symbol, dtype=float)
        return StockHistory(series, datetime(2026, 10, 19, tzinfo=timezone.utc), "https://finance.yahoo.com")

    st.cache_data.clear()
    monkeypatch.setattr(market_data, "fetch_history", history)
    return AppTest.from_file(str(APP), default_timeout=20)


def figures(app):
    return [json.loads(element.proto.spec) for element in app.get("plotly_chart")]


def test_default_app_has_five_charts_identity_and_correct_returns(app):
    app.run()
    assert not app.exception
    assert app.multiselect[0].value == ["AAPL", "MSFT", "NVDA"]
    assert len(figures(app)) == 5
    assert [metric.value for metric in app.metric] == ["+19.79%", "+5.00%", "+40.00%"]
    text = " ".join(element.value for element in app.markdown)
    assert "Braulio Lora Encarnacion" in text and "Developed for CPS*5745" in text


def test_changing_shared_company_filter_updates_all_charts_and_findings(app):
    app.run()
    app.multiselect[0].set_value(["MSFT", "NVDA"]).run()
    assert not app.exception
    assert len(figures(app)) == 5
    assert all("Apple" not in json.dumps(figure) for figure in figures(app))
    findings = [element.value for element in app.markdown if element.value.startswith("- ")]
    assert findings and all("Apple" not in finding for finding in findings)
    assert len(app.metric) == 2


def test_changing_shared_date_filter_updates_charts_metrics_and_findings(app):
    app.run()
    before = figures(app)
    before_findings = [element.value for element in app.markdown if element.value.startswith("- ")]
    app.date_input[0].set_value((date(2026, 10, 14), date(2026, 10, 16))).run()
    assert not app.exception
    after = figures(app)
    assert all(old != new for old, new in zip(before, after))
    assert app.metric[0].value == "+21.00%"
    assert len(after[0]["data"][0]["x"]) == 3
    findings = [element.value for element in app.markdown if element.value.startswith("- ")]
    assert findings != before_findings


def test_empty_selection_and_insufficient_data_do_not_crash(app):
    app.run()
    app.multiselect[0].set_value([]).run()
    assert not app.exception and len(figures(app)) == 0
    assert any("at least one company" in message.value for message in app.info)
    app.multiselect[0].set_value(["AAPL"]).run()
    app.date_input[0].set_value((date(2026, 10, 15), date(2026, 10, 16))).run()
    assert not app.exception and len(figures(app)) == 0
    assert any("three shared" in message.value for message in app.warning)


def test_download_failure_is_visible_and_no_partial_charts_are_shown(monkeypatch):
    def fail(symbol):
        raise DataDownloadError(f"Could not download {symbol}. connection failed or timed out")

    st.cache_data.clear()
    monkeypatch.setattr(market_data, "fetch_history", fail)
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    assert not app.exception and len(figures(app)) == 0
    assert len(app.error) == 1
    assert len(app.warning) == 3
