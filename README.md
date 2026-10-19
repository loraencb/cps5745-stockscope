# StockScope

A Python, Streamlit, and Plotly dashboard comparing Apple (AAPL), Microsoft (MSFT), and NVIDIA (NVDA).

**Braulio Lora Encarnacion**  
**Developed for CPS*5745**

## Live dashboard

**[Open StockScope](https://braulio-stockscope.streamlit.app/)**

The app is deployed on Streamlit Community Cloud using Python 3.12. It was verified in a fresh signed-out Chrome session on October 19, 2026: all five charts, both shared filters, dynamic findings, and the actual return calculations passed. No sign-in is needed to view it.

Source repository: https://github.com/loraencb/cps5745-stockscope

Download [the complete project and submission bundle](StockScope_Quiz.zip) for the source, screenshots, and submission notes. After extracting it, the three submission screenshots are in `submission/deployed_screenshots/`. The matching `verification.json` records the public URL, time, selected dates, calculations, and successful checks. See `submission/SUBMISSION.md` for the ready-to-submit materials.

## Run locally

Use Python 3.12. From this Quiz folder, run:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the local URL printed by Streamlit, usually `http://localhost:8501`.
No API key is required. An internet connection is required for stock downloads.

## Use the dashboard

- All three companies are selected initially.
- The default date range is the latest year ending on the latest available common trading date.
- The company and date filters update all five charts, summary cards, and Key Findings together.
- Click **Refresh market data** to bypass the 15-minute download cache.
- The selected period, latest available trading date, data source, and refresh timestamp are shown above the charts.
- Prices are downloaded for the last five years. Dates in the filter are inclusive.
- A failed download is shown clearly, and the app does not silently show a partial comparison or invented data.

## The five comparisons

1. **Indexed performance line chart:** every stock starts at 100 on the same comparison date. This compares growth without making a high share price look like better performance.
2. **Period-return bar chart:** compares percentage change from each company's first adjusted close to its last adjusted close in the selected period. A zero baseline separates gains and losses.
3. **Daily-return box plot:** compares the median, middle 50%, whiskers within 1.5 times the interquartile range, and unusually large moves. A wider spread means more day-to-day variation.
4. **Daily-return histogram:** shows how often each size of daily gain or loss occurred. Each company has a panel with the same 30 bins and identical axis scales. Heights are percentages of daily observations.
5. **Correlation heatmap:** compares Pearson correlations between companies' aligned daily returns. The scale is fixed from -1 to +1. A correlation does not establish cause and effect.

## Calculations and price policy

Let `A_t` be Yahoo Finance's adjusted close for a trading date.

- Indexed value: `100 * A_t / A_first`.
- Period return (%): `100 * (A_last / A_first - 1)`.
- Daily return (%): `100 * (A_t / A_previous_trading_day - 1)`.
- Daily-return standard deviation in Key Findings uses the sample formula (`ddof=1`).
- The heatmap uses Pearson correlation on the same shared daily observations.

Yahoo's adjusted closes account for stock splits and cash dividend distributions. These are adjusted-price returns, used as a **total-return proxy**, rather than unadjusted price returns. This is not an exact cash-flow simulation of reinvesting dividends. Fees and taxes are excluded. All three stocks are quoted in USD.

The first and last prices are taken from dates with valid quotes for every selected company. There is no forward filling. Daily returns are calculated before removing missing quotes so a missing date never becomes an invented multi-day "daily" return. A current, unfinished session is excluded; today's close becomes eligible 15 minutes after the exchange-reported session end, including early-close days. If the provider does not supply today's session end, 16:15 America/New_York time is used. The displayed refresh timestamp is the oldest successful download among the selected companies.

The Yahoo chart endpoint is tried on `query1.finance.yahoo.com`, then `query2.finance.yahoo.com`. The app checks for valid adjusted prices and reports HTTP, connectivity, or malformed-data failures. It does not substitute unadjusted prices or synthetic data.

Provider policy: https://help.yahoo.com/kb/SLN28256.html

## Test

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

The tests include hand-calculated compounded returns, the common starting date, inclusive date filtering, missing-quote handling, correlation, common histogram bins/scales, unfinished sessions, and Streamlit widget interactions. Test prices are explicitly synthetic fixtures and are used only inside the tests, never in the dashboard.

For real browser checks against a running local or deployed app:

```powershell
.\.venv\Scripts\python.exe scripts\verify_browser.py http://localhost:8501 --output submission\local_preview
```

This uses an installed Google Chrome browser in a fresh, signed-out test session. For the public app, run:

```powershell
.\.venv\Scripts\python.exe scripts\verify_browser.py https://braulio-stockscope.streamlit.app/ --output submission\deployed_screenshots
```

The script supports the signed-out Streamlit Cloud iframe as well as the local app. It checks the actual CSV-backed return calculations and both filters, then saves screenshots and a machine-readable report. Local previews are not evidence of a public deployment.

## Deploy to Streamlit Community Cloud

1. Put this folder's application files in a GitHub repository. Do not upload `.venv`, secrets, or the quiz PDF.
2. Sign in at https://share.streamlit.io and choose **Create app** → **Yup, I have an app**.
3. Select the repository, the `main` branch, and `app.py` as the entrypoint.
4. Choose Python 3.12 in Advanced settings and deploy. No secrets are needed.
5. Ensure the app is public. A public repository produces a public app by default; check the app's Sharing setting if needed.
6. Open the deployed URL in a signed-out or private browser. Test both filters and check the data timestamp.
7. Capture screenshots that together show all five charts, the selected filters, the name, and the exact course statement.

The same Python application can run on another host that supports a long-running Streamlit process and WebSockets. Set the command to `streamlit run app.py --server.address 0.0.0.0 --server.port $PORT` where supported.

## Design reference

The reference linked in Question 12 is Kean's enrollment dashboard:

https://app.powerbi.com/view?r=eyJrIjoiMDE3OTIwNzUtODFmZS00NmUzLWExOWEtZmFkMGJiNTM5NTA5IiwidCI6IjkyMDIwZTU1LTc2NmEtNGJhYS1hMjc3LTk0YTI0ZjFiMTFiNyIsImMiOjR9

StockScope follows its navy header, shared filters, summary indicators, and coordinated chart panels. The actual stock charts use normalized values and returns appropriate for comparing companies.

This is a classroom visualization project, not investment advice.
