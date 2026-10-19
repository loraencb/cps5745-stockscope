from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from analytics import SelectionError, compare, histogram_bins, key_findings
from charts import box_chart, correlation_chart, histogram_chart, performance_chart, return_chart
from market_data import DataDownloadError, parse_history


@pytest.fixture
def prices():
    return pd.DataFrame({"AAPL": [100, 110, 99, 108.9, 119.79],
                         "MSFT": [200, 202, 198, 205, 210],
                         "NVDA": [50, 55, 52, 60, 70]},
                        index=pd.date_range("2026-10-12", periods=5, freq="B"))


def test_compounded_return_is_not_the_sum_of_daily_returns(prices):
    result = compare(prices, ["AAPL"], "2026-10-12", "2026-10-14")
    assert result.daily_returns.AAPL.tolist() == pytest.approx([10, -10])
    assert result.period_returns.AAPL == pytest.approx(-1)
    assert result.indexed.AAPL.iloc[-1] == pytest.approx(99)
    assert result.daily_returns.AAPL.sum() == pytest.approx(0)


def test_company_and_inclusive_date_filter_control_every_result(prices):
    result = compare(prices, ["MSFT", "NVDA"], "2026-10-14", "2026-10-16")
    assert result.prices.index.tolist() == prices.index[2:].tolist()
    assert result.prices.columns.tolist() == ["MSFT", "NVDA"]
    assert (result.indexed.iloc[0] == 100).all()
    assert result.period_returns.MSFT == pytest.approx((210 / 198 - 1) * 100)
    assert result.period_returns.NVDA == pytest.approx((70 / 52 - 1) * 100)
    assert len(result.daily_returns) == 2
    assert result.correlations.shape == (2, 2)
    assert all("Apple" not in finding for finding in key_findings(result))


def test_same_baseline_when_one_company_starts_later(prices):
    prices.loc[prices.index[0], "MSFT"] = np.nan
    result = compare(prices, ["AAPL", "MSFT"], "2026-10-12", "2026-10-16")
    assert result.prices.index[0] == pd.Timestamp("2026-10-13")
    assert result.indexed.iloc[0].tolist() == [100, 100]
    assert result.period_returns.AAPL == pytest.approx((119.79 / 110 - 1) * 100)


def test_missing_quote_is_not_filled_or_bridged(prices):
    prices.loc[prices.index[2], "AAPL"] = np.nan
    result = compare(prices, ["AAPL", "MSFT"], "2026-10-12", "2026-10-16")
    assert result.daily_returns.index.tolist() == [prices.index[1], prices.index[4]]
    assert result.excluded_dates == 1
    assert result.daily_returns.AAPL.iloc[-1] == pytest.approx(10)


@pytest.mark.parametrize("symbols,start,end,match", [
    ([], "2026-10-12", "2026-10-16", "at least one company"),
    (["AAPL"], "2026-10-16", "2026-10-12", "start date"),
    (["AAPL"], "2026-10-12", "2026-10-13", "three shared"),
    (["AAPL"], "2020-01-01", "2020-01-05", "three shared"),
    (["MISSING"], "2026-10-12", "2026-10-16", "not available"),
])
def test_invalid_selections_have_clear_messages(prices, symbols, start, end, match):
    with pytest.raises(SelectionError, match=match):
        compare(prices, symbols, start, end)


def test_correlation_and_daily_standard_deviation_match_independent_calculations(prices):
    result = compare(prices, list(prices), prices.index[0], prices.index[-1])
    expected = 100 * (prices.to_numpy()[1:] / prices.to_numpy()[:-1] - 1)
    np.testing.assert_allclose(result.daily_returns, expected)
    np.testing.assert_allclose(result.correlations, np.corrcoef(expected, rowvar=False))
    np.testing.assert_allclose(result.daily_returns.std(ddof=1), np.std(expected, axis=0, ddof=1))
    assert "NVIDIA" in key_findings(result)[0]
    assert "+40.00%" in key_findings(result)[0]


def test_histograms_share_identical_bins_and_axes(prices):
    result = compare(prices, list(prices), prices.index[0], prices.index[-1])
    edges = histogram_bins(result.daily_returns)
    for symbol in prices:
        counts, _ = np.histogram(result.daily_returns[symbol], bins=edges)
        assert counts.sum() == len(result.daily_returns)
    figure = histogram_chart(result)
    assert len({(trace.xbins.start, trace.xbins.end, trace.xbins.size) for trace in figure.data}) == 1
    assert figure.layout.xaxis.range == figure.layout.xaxis2.range == figure.layout.xaxis3.range
    assert figure.layout.yaxis.range == figure.layout.yaxis2.range == figure.layout.yaxis3.range


def test_all_five_chart_types_use_the_filtered_companies(prices):
    result = compare(prices, ["MSFT", "NVDA"], "2026-10-14", "2026-10-16")
    figures = [performance_chart(result), return_chart(result), histogram_chart(result),
               box_chart(result), correlation_chart(result)]
    assert [fig.data[0].type for fig in figures] == ["scatter", "bar", "histogram", "box", "heatmap"]
    assert list(figures[0].data[0].y)[0] == 100
    assert list(figures[1].data[0].y) == pytest.approx(result.period_returns.tolist())
    assert all("Apple" not in fig.to_json() for fig in figures)
    assert all(fig.layout.title.text for fig in figures)


def test_constant_series_and_one_company_remain_valid():
    prices = pd.DataFrame({"AAPL": [100.0] * 5}, index=pd.date_range("2026-10-12", periods=5, freq="B"))
    result = compare(prices, ["AAPL"], prices.index[0], prices.index[-1])
    assert result.period_returns.AAPL == 0
    assert np.isnan(result.correlations.iloc[0, 0])
    assert correlation_chart(result).data[0].text[0][0] == "N/A"
    assert len(key_findings(result)) == 3


def payload_for(dates, adjusted):
    timestamps = [int(pd.Timestamp(date, tz="America/New_York").replace(hour=9, minute=30).timestamp())
                  for date in dates]
    return {"chart": {"result": [{"timestamp": timestamps,
                                "indicators": {"adjclose": [{"adjclose": adjusted}],
                                               "quote": [{"close": [9999] * len(dates)}]}}], "error": None}}


def test_provider_uses_adjusted_close_and_excludes_unfinished_today():
    payload = payload_for(["2026-10-14", "2026-10-15", "2026-10-16", "2026-10-19"], [90, 91, 92, 93])
    before_close = datetime(2026, 10, 19, 18, 0, tzinfo=timezone.utc)
    result = parse_history(payload, "AAPL", before_close)
    assert result.tolist() == [90, 91, 92]
    after_close = datetime(2026, 10, 19, 21, 0, tzinfo=timezone.utc)
    assert parse_history(payload, "AAPL", after_close).tolist() == [90, 91, 92, 93]


def test_provider_does_not_silently_substitute_unadjusted_prices():
    payload = payload_for(["2026-10-14", "2026-10-15", "2026-10-16"], [90, 91, 92])
    del payload["chart"]["result"][0]["indicators"]["adjclose"]
    with pytest.raises(DataDownloadError, match="adjusted-close"):
        parse_history(payload, "AAPL", datetime(2026, 10, 19, tzinfo=timezone.utc))


def test_provider_respects_an_exchange_reported_early_close():
    payload = payload_for(["2026-11-23", "2026-11-24", "2026-11-25", "2026-11-27"], [90, 91, 92, 93])
    close = int(pd.Timestamp("2026-11-27 13:00", tz="America/New_York").timestamp())
    payload["chart"]["result"][0]["meta"] = {"currentTradingPeriod": {"regular": {"end": close}}}
    after_close = datetime(2026, 11, 27, 18, 16, tzinfo=timezone.utc)
    assert parse_history(payload, "AAPL", after_close).tolist() == [90, 91, 92, 93]
