"""Download daily adjusted closes from Yahoo Finance."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

COMPANIES = {"AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA"}
COLORS = {"AAPL": "#3478F6", "MSFT": "#8B5CF6", "NVDA": "#00A878"}
SOURCE = "Yahoo Finance · daily adjusted close"
NY = ZoneInfo("America/New_York")


class DataDownloadError(Exception):
    pass


@dataclass
class StockHistory:
    prices: pd.Series
    refreshed_at: datetime
    url: str


def parse_history(payload, symbol, now):
    """Keep valid adjusted prices and exclude a still-open trading session."""
    chart = payload.get("chart", {})
    if chart.get("error") or not chart.get("result"):
        raise DataDownloadError(f"{symbol}: the provider returned no price history.")
    result = chart["result"][0]
    timestamps = result.get("timestamp", [])
    adjusted_sets = result.get("indicators", {}).get("adjclose") or [{}]
    adjusted = adjusted_sets[0].get("adjclose", [])
    if not timestamps or len(timestamps) != len(adjusted):
        raise DataDownloadError(f"{symbol}: adjusted-close data is missing or incomplete.")

    dates = pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(NY)
    dates = dates.normalize().tz_localize(None)
    prices = pd.Series(adjusted, index=dates, name=symbol, dtype=float)
    prices = prices.replace([np.inf, -np.inf], np.nan).dropna()
    prices = prices[prices > 0]
    prices = prices[~prices.index.duplicated(keep="last")].sort_index()
    local_now = now.astimezone(NY)
    # Use the exchange-reported close, including early-close sessions, plus 15 minutes.
    cutoff = pd.Timestamp(local_now.date())
    prices = prices[prices.index <= cutoff]
    close = datetime.combine(local_now.date(), time(16), tzinfo=NY)
    regular_end = result.get("meta", {}).get("currentTradingPeriod", {}).get("regular", {}).get("end")
    if isinstance(regular_end, (int, float)):
        reported_close = datetime.fromtimestamp(regular_end, NY)
        if reported_close.date() == local_now.date():
            close = reported_close
    if local_now < close + timedelta(minutes=15):
        prices = prices[prices.index < cutoff]
    if len(prices) < 3:
        raise DataDownloadError(f"{symbol}: fewer than three completed daily closes are available.")
    prices.index.name = "Date"
    return prices


def fetch_history(symbol):
    if symbol not in COMPANIES:
        raise ValueError("Choose AAPL, MSFT, or NVDA.")
    failures = []
    for host in ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]:
        url = f"https://{host}/v8/finance/chart/{symbol}"
        try:
            response = requests.get(
                url,
                params={"range": "5y", "interval": "1d", "events": "div,splits"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=(5, 15),
            )
            response.raise_for_status()
            now = datetime.now(timezone.utc)
            return StockHistory(parse_history(response.json(), symbol, now), now, url)
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError,
                DataDownloadError) as error:
            if isinstance(error, requests.HTTPError):
                reason = f"HTTP {error.response.status_code}"
            elif isinstance(error, requests.RequestException):
                reason = "connection failed or timed out"
            else:
                reason = "no usable adjusted-price history"
            failures.append(f"{host}: {reason}")
    raise DataDownloadError(f"Could not download {symbol}. " + "; ".join(failures))
