"""CPS*5745 stock comparison dashboard. Run with: streamlit run app.py"""

from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from analytics import SelectionError, compare, key_findings
from charts import box_chart, correlation_chart, histogram_chart, performance_chart, return_chart
from market_data import COLORS, COMPANIES, SOURCE, DataDownloadError, fetch_history

st.set_page_config(page_title="StockScope | Braulio Lora Encarnacion", page_icon="📈",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { background: #f5f7fb; }
    .block-container { padding-top: 1.7rem; padding-bottom: 2rem; max-width: 1450px; }
    [data-testid="stSidebar"] { background: #fff; border-right: 1px solid #e3e9f1; }
    [data-testid="stSidebar"] .block-container { padding-top: 2rem; }
    .hero { background: #122744; border-radius: 14px; padding: 26px 30px;
            margin-bottom: 20px; color: #fff; }
    .hero .eyebrow { font-size: 11px; letter-spacing: 2px; color: #a7c5ef; margin-bottom: 8px; }
    .hero h1 { color: #fff; font-size: 34px; font-weight: 650; margin: 0; padding: 0; }
    .hero p { color: #dbe6f6; font-size: 15px; margin: 8px 0 0; }
    .hero .credit { color: #dbe6f6; font-size: 13px; margin-top: 18px; }
    .hero .course { display: inline-block; padding: 3px 9px; background: #264260;
                   border-radius: 5px; margin-left: 10px; color: #fff; }
    [data-testid="stMetric"] { background: white; border: 1px solid #e3e9f1;
                               border-radius: 11px; padding: 14px 18px; }
    [data-testid="stVerticalBlockBorderWrapper"] > div { border-radius: 11px; }
    [data-testid="stPlotlyChart"] { border-radius: 10px; overflow: hidden; }
    h2 { color: #122744; font-size: 24px !important; }
    .small-label { color: #64748b; font-size: 12px; line-height: 1.7; }
    .company-key { font-size: 12px; color: #475569; margin-bottom: 4px; }
    .author { border-top: 1px solid #e3e9f1; padding-top: 15px; margin-top: 24px;
              color: #475569; font-size: 12px; line-height: 1.8; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <div class="eyebrow">CPS*5745 · QUESTION 12</div>
    <h1>StockScope</h1>
    <p>One clear view of Apple, Microsoft, and NVIDIA.</p>
    <div class="credit">Braulio Lora Encarnacion
        <span class="course">Developed for CPS*5745</span>
    </div>
</div>
""", unsafe_allow_html=True)


@st.cache_data(ttl=900, show_spinner=False)
def load_history(symbol):
    return fetch_history(symbol)


def plot(figure):
    st.plotly_chart(figure, width="stretch", config={"displaylogo": False,
                    "modeBarButtonsToRemove": ["lasso2d", "select2d"]})


with st.sidebar:
    st.markdown("## Compare companies")
    st.caption("These filters control all five charts and the Key Findings.")
    symbols = st.multiselect("Companies", list(COMPANIES), default=list(COMPANIES),
                             format_func=lambda symbol: f"{COMPANIES[symbol]} ({symbol})",
                             key="companies")
    refresh = st.button("Refresh market data", width="stretch")
    if refresh:
        load_history.clear()
    st.markdown('<div class="author"><strong>Braulio Lora Encarnacion</strong><br>'
                'Developed for CPS*5745</div>', unsafe_allow_html=True)

if not symbols:
    st.info("Select at least one company to see the dashboard.")
    st.stop()

histories = {}
errors = []
with st.spinner("Getting the latest completed daily closes from Yahoo Finance..."):
    for symbol in symbols:
        try:
            histories[symbol] = load_history(symbol)
        except DataDownloadError as error:
            errors.append(str(error))
if errors:
    st.error("Market data could not be downloaded. No partial comparison is being shown.")
    for error in errors:
        st.warning(error)
    st.info("Try Refresh market data. You can also deselect an unavailable company. "
            "This app never replaces a failed download with invented prices.")
    st.caption("Source: Yahoo Finance · daily adjusted close")
    st.stop()

prices = pd.concat([histories[symbol].prices for symbol in symbols], axis=1).sort_index()
available = prices.dropna(how="any")
if len(available) < 3:
    st.warning("There are not enough shared trading dates for these companies.")
    st.stop()
earliest, latest = available.index[0].date(), available.index[-1].date()
default_start = max(earliest, (pd.Timestamp(latest) - pd.DateOffset(years=1)).date())

with st.sidebar:
    date_range = st.date_input("Date range", value=(default_start, latest),
                               min_value=earliest, max_value=latest, key="date_range",
                               format="YYYY-MM-DD")
    st.caption("Default: the latest year available. Prices load for up to five years.")
    st.markdown("---")
    st.markdown("**Company colors**")
    for symbol in symbols:
        st.markdown(f'<div class="company-key"><span style="color:{COLORS[symbol]}">●</span> '
                    f'{COMPANIES[symbol]} ({symbol})</div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("**Return basis**")
    st.caption("Adjusted close accounts for splits and cash dividends. These are adjusted-price "
               "returns, used as a total-return proxy, before fees and taxes.")

if len(date_range) != 2:
    st.info("Choose both a start date and an end date.")
    st.stop()
try:
    comparison = compare(prices, symbols, *date_range)
except SelectionError as error:
    st.warning(str(error))
    st.stop()

first, last = comparison.prices.index[0], comparison.prices.index[-1]
oldest_refresh = min(history.refreshed_at for history in histories.values())
st.markdown(f"**{first:%b %d, %Y} – {last:%b %d, %Y}** · "
            f"{len(symbols)} companies · {len(comparison.prices):,} shared closing dates")
st.caption(f"Source: {SOURCE} | Latest available trading date: {latest:%b %d, %Y} | "
           f"Last successful refresh: {oldest_refresh:%Y-%m-%d %H:%M:%S} UTC")
if latest < (datetime.now(timezone.utc).date() - timedelta(days=7)):
    st.warning("The provider's latest completed close is more than a week old. "
               "The dates above show exactly how current this comparison is.")

cards = st.columns(len(symbols))
for column, symbol in zip(cards, symbols):
    with column:
        st.metric(f"{COMPANIES[symbol]} · {symbol}",
                  f"{comparison.period_returns[symbol]:+.2f}%")
st.caption("Adjusted return over the selected period · each company uses the same first and last dates.")

with st.container(border=True):
    plot(performance_chart(comparison))
    st.caption(f"All selected stocks start at 100 on {first:%b %d, %Y}. "
               "A value of 120 means a 20% adjusted gain from that shared starting point.")

left, right = st.columns(2)
with left, st.container(border=True):
    plot(return_chart(comparison))
    st.caption("Each bar compares the first and last adjusted close in the selected period.")
with right, st.container(border=True):
    plot(box_chart(comparison))
    st.caption("The box shows the middle 50% of daily returns. The center line is the median; "
               "whiskers extend to observations within 1.5 IQR, and dots show outliers.")

with st.container(border=True):
    plot(histogram_chart(comparison))
    st.caption("Every panel uses identical bins and identical x- and y-axis ranges. "
               "Bar height is the percentage of shared daily observations in that return range.")

left, right = st.columns([1.05, 1])
with left, st.container(border=True):
    plot(correlation_chart(comparison))
    st.caption("Pearson r ranges from -1 to +1. Positive values mean daily returns tended "
               "to move together. N/A means a return series did not vary.")
with right, st.container(border=True):
    st.markdown("## Key Findings")
    st.caption(f"Based only on the selected companies, {first:%b %d, %Y} to {last:%b %d, %Y}.")
    for finding in key_findings(comparison):
        st.markdown(f"- {finding}")

with st.expander("How the comparisons work", expanded=False):
    st.markdown("""
    - **Indexed performance:** 100 × adjusted close ÷ first adjusted close.
    - **Period return (%):** 100 × (last adjusted close ÷ first adjusted close − 1).
    - **Daily return (%):** 100 × (today's adjusted close ÷ previous trading day's adjusted close − 1).
    - **Correlation:** Pearson correlation of the same companies' shared daily percentage returns.
    - **Adjustment policy:** Yahoo adjusts past closes for stock splits and dividend distributions.
      Adjusted-price returns are a total-return proxy, not unadjusted price returns. They are not
      an exact cash-flow simulation of dividend reinvestment and exclude fees and taxes.
    - **Dates:** The selected date range is inclusive. The charts use common trading dates.
      No prices are forward-filled, and daily returns never bridge a missing quote.
      An unfinished current trading session is excluded. Today's close is eligible 15 minutes after
      the exchange-reported session end (normally 16:15 ET, earlier on early-close days).
    - **Refresh:** Successful downloads are cached for 15 minutes. The refresh button downloads
      again. The displayed refresh time is the oldest successful download among the selected stocks.
    """)
    st.write(f"Daily-return charts use {len(comparison.daily_returns):,} shared observations. "
             f"{comparison.excluded_dates} incomplete closing dates were excluded from price comparisons.")
    st.markdown("[Yahoo's adjusted-close policy](https://help.yahoo.com/kb/SLN28256.html)")
    st.markdown("Design reference: [Kean Power BI dashboard](https://app.powerbi.com/view?"
                "r=eyJrIjoiMDE3OTIwNzUtODFmZS00NmUzLWExOWEtZmFkMGJiNTM5NTA5IiwidCI6"
                "IjkyMDIwZTU1LTc2NmEtNGJhYS1hMjc3LTk0YTI0ZjFiMTFiNyIsImMiOjR9). "
                "The navy header, shared filtering, and coordinated chart panels follow its approach.")

csv = comparison.prices.to_csv().encode("utf-8")
st.download_button("Download selected adjusted closes (CSV)", csv,
                   file_name="selected_adjusted_closes.csv", mime="text/csv")
st.caption("Braulio Lora Encarnacion · Developed for CPS*5745 · Classroom data visualization project")
