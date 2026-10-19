"""The shared filtering and calculations behind all five charts."""

from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd

from market_data import COMPANIES


class SelectionError(ValueError):
    pass


@dataclass
class Comparison:
    prices: pd.DataFrame
    indexed: pd.DataFrame
    period_returns: pd.Series
    daily_returns: pd.DataFrame
    correlations: pd.DataFrame
    excluded_dates: int


def compare(prices, symbols, start, end):
    if not symbols:
        raise SelectionError("Select at least one company to see the dashboard.")
    if pd.Timestamp(start) > pd.Timestamp(end):
        raise SelectionError("The start date must be on or before the end date.")
    if not set(symbols).issubset(prices.columns):
        raise SelectionError("Price data is not available for every selected company.")
    window = prices.loc[pd.Timestamp(start):pd.Timestamp(end), list(symbols)].copy()
    window = window.replace([np.inf, -np.inf], np.nan).where(lambda values: values > 0)
    common = window.dropna(how="any")
    if len(common) < 3:
        raise SelectionError("Choose a wider date range with at least three shared trading dates.")
    # Calculate before dropping missing dates: never bridge a missing quote or forward-fill it.
    window = window.loc[common.index[0]:common.index[-1]]
    daily = window.pct_change(fill_method=None).dropna(how="any") * 100
    if len(daily) < 2:
        raise SelectionError("Not enough shared daily returns. Choose a wider date range.")
    indexed = common.div(common.iloc[0]).mul(100)
    period = (common.iloc[-1].div(common.iloc[0]) - 1) * 100
    return Comparison(common, indexed, period, daily, daily.corr(), len(window) - len(common))


def histogram_bins(daily_returns, count=30):
    """One set of bin edges, used unchanged for every company."""
    return np.histogram_bin_edges(daily_returns.to_numpy().ravel(), bins=count)


def key_findings(comparison):
    period = comparison.period_returns
    daily = comparison.daily_returns
    symbols = list(period.index)
    best, worst = period.idxmax(), period.idxmin()
    start = comparison.prices.index[0].strftime("%b %d, %Y")
    end = comparison.prices.index[-1].strftime("%b %d, %Y")

    if len(symbols) == 1:
        findings = [f"{COMPANIES[best]}'s adjusted return was {period[best]:+.2f}% "
                    f"from {start} to {end}."]
    elif np.isclose(period.max(), period.min()):
        findings = [f"The selected companies finished with the same adjusted return "
                    f"({period[best]:+.2f}%) from {start} to {end}."]
    else:
        gap = period[best] - period[worst]
        findings = [f"{COMPANIES[best]} had the strongest adjusted return ({period[best]:+.2f}%), "
                    f"while {COMPANIES[worst]} returned {period[worst]:+.2f}%. "
                    f"The difference was {gap:.2f} percentage points over the selected period."]

    volatility = daily.std(ddof=1)
    high, low = volatility.idxmax(), volatility.idxmin()
    if len(symbols) > 1 and not np.isclose(volatility.max(), volatility.min()):
        findings.append(f"{COMPANIES[high]} moved around the most day to day. Its daily-return "
                        f"standard deviation was {volatility[high]:.2f}%, compared with "
                        f"{volatility[low]:.2f}% for {COMPANIES[low]}.")
    else:
        findings.append(f"Daily-return standard deviation was about {volatility[high]:.2f}%. "
                        "This describes how widely daily gains and losses varied.")

    pairs = [(a, b, comparison.correlations.loc[a, b]) for a, b in combinations(symbols, 2)]
    pairs = [pair for pair in pairs if np.isfinite(pair[2])]
    if pairs:
        a, b, correlation = max(pairs, key=lambda pair: pair[2])
        findings.append(f"{COMPANIES[a]} and {COMPANIES[b]} had the highest daily-return "
                        f"correlation (r = {correlation:.2f}). Correlation describes how their "
                        "daily moves lined up; it does not show that one caused the other.")
    elif len(symbols) == 1:
        findings.append("Select another company to compare how their daily returns move together.")
    else:
        findings.append("A correlation is undefined when a company's daily returns do not vary.")
    return findings
