"""Verify a running app in a fresh browser and capture its actual screenshots."""

import argparse
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from playwright.sync_api import expect, sync_playwright


def snapshots(page):
    return page.locator(".js-plotly-plot").evaluate_all("""elements => elements.map(e => ({
        title: e.layout.title.text,
        data: e.data.map(t => ({type:t.type, name:t.name, x:t.x || [], y:t.y || [],
                               z:t.z || [], xbins:t.xbins || null})),
        xRange: e.layout.xaxis?.range,
        yRange: e.layout.yaxis?.range
    }))""")


def findings(page):
    return page.get_by_role("heading", name="Key Findings").evaluate(
        "e => e.closest('[data-testid=stVerticalBlock]').innerText")


def capture(page, directory, browser_page):
    main = page.get_by_test_id("stMain")
    main.evaluate("e => e.scrollTop = 0")
    browser_page.screenshot(path=str(directory / "01_overview_and_performance.png"))
    chart = page.get_by_test_id("stPlotlyChart").nth(1)
    chart.evaluate("e => {const m=e.closest('[data-testid=stMain]'); "
                   "m.scrollTop += e.getBoundingClientRect().top - m.getBoundingClientRect().top - 95;}")
    browser_page.screenshot(path=str(directory / "02_return_spread_and_histograms.png"))
    main.evaluate("e => e.scrollTop = e.scrollHeight")
    browser_page.screenshot(path=str(directory / "03_correlation_and_findings.png"))


def verify(url, directory):
    directory.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1100}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
        assert response and response.status < 400
        browser_page = page
        # Community Cloud serves the app inside an iframe for signed-out visitors.
        page.wait_for_function("""() => document.querySelector('.js-plotly-plot') ||
            [...document.querySelectorAll('iframe')].some(e => e.src.includes('/~/+/'))""",
            timeout=60000)
        if not page.locator(".js-plotly-plot").count():
            iframe = browser_page.locator('iframe[src*="/~/+/"]')
            iframe.wait_for(state="attached")
            page = iframe.element_handle().content_frame()
            assert page, "The Streamlit application frame did not load."
        page.locator(".js-plotly-plot").nth(4).wait_for(timeout=60000)
        expect(page.get_by_test_id("stException")).to_have_count(0)
        plots = snapshots(page)
        assert [plot["data"][0]["type"] for plot in plots] == ["scatter", "bar", "box", "histogram", "heatmap"]
        assert len(plots[0]["data"]) == 3
        assert "Braulio Lora Encarnacion" in page.locator("body").inner_text()
        assert "Developed for CPS*5745" in page.locator("body").inner_text()
        assert "Yahoo Finance" in page.locator("body").inner_text()

        with browser_page.expect_download() as pending:
            page.get_by_test_id("stDownloadButton").get_by_role("button").click()
        download = pending.value
        csv = Path(download.path()).read_text(encoding="utf-8")
        prices = pd.read_csv(StringIO(csv), index_col=0, parse_dates=True)
        assert list(prices) == ["AAPL", "MSFT", "NVDA"]
        expected_period = 100 * (prices.iloc[-1] / prices.iloc[0] - 1)
        expected_daily = 100 * (prices.to_numpy()[1:] / prices.to_numpy()[:-1] - 1)
        np.testing.assert_allclose(plots[1]["data"][0]["y"], expected_period, atol=1e-9)
        for i, symbol in enumerate(prices):
            np.testing.assert_allclose(plots[0]["data"][i]["y"], 100 * prices[symbol] / prices[symbol].iloc[0], atol=1e-9)
            assert plots[0]["data"][i]["y"][0] == 100
            np.testing.assert_allclose(plots[2]["data"][i]["y"], expected_daily[:, i], atol=1e-9)
            np.testing.assert_allclose(plots[3]["data"][i]["x"], expected_daily[:, i], atol=1e-9)
        np.testing.assert_allclose(plots[4]["data"][0]["z"], np.corrcoef(expected_daily, rowvar=False), atol=1e-9)
        assert page.get_by_test_id("stMetricValue").all_text_contents() == [f"{value:+.2f}%" for value in expected_period]
        initial_dates = page.get_by_test_id("stDateInput").locator("input").evaluate_all("es=>es.map(e=>e.value)")
        initial_findings = findings(page)
        capture(page, directory, browser_page)

        # A real company-widget change must update every plotted dataset and the findings.
        page.get_by_role("button", name="Remove Microsoft (MSFT)", exact=True).click()
        page.wait_for_function("""() => {
            const p = [...document.querySelectorAll('.js-plotly-plot')];
            return p.length===5 && p[0].data.length===2 && p[1].data[0].x.length===2
                   && p[2].data.length===2 && p[3].data.length===2 && p[4].data[0].x.length===2;
        }""")
        company_plots = snapshots(page)
        assert all("Microsoft" not in json.dumps(plot) for plot in company_plots)
        assert "Microsoft" not in findings(page)
        assert len(page.get_by_test_id("stMetricValue").all_text_contents()) == 2

        # Move the start month with the actual accessible date control.
        month = page.get_by_role("spinbutton", name="month, Date range start date", exact=True)
        month.click()
        month.press("ArrowUp")
        page.get_by_role("heading", name="Compare companies", exact=True).click()
        old_first = company_plots[0]["data"][0]["x"][0]
        page.wait_for_function("old => {const p=document.querySelector('.js-plotly-plot'); "
                               "return p?.data?.[0]?.x?.length && p.data[0].x[0] !== old;}", arg=old_first)
        page.locator(".js-plotly-plot").nth(4).wait_for()
        page.wait_for_function("""() => !document.querySelector('[data-testid=stStatusWidget]')?.innerText.includes('Running')""")
        changed_plots = snapshots(page)
        assert all(old["data"] != new["data"] for old, new in zip(company_plots, changed_plots))
        assert findings(page) != initial_findings
        changed_dates = page.get_by_test_id("stDateInput").locator("input").evaluate_all("es=>es.map(e=>e.value)")
        assert changed_dates != initial_dates

        page.get_by_test_id("stMultiSelect").get_by_role("button", name="Clear all", exact=True).click()
        expect(page.get_by_text("Select at least one company to see the dashboard.", exact=True)).to_be_visible()
        expect(page.get_by_test_id("stPlotlyChart")).to_have_count(0)
        expect(page.get_by_test_id("stException")).to_have_count(0)
        assert not errors, errors

        report = {
            "url": url, "final_url": browser_page.url, "app_frame_url": page.url, "verified_at_utc": datetime.now(timezone.utc).isoformat(),
            "browser_session": "fresh signed-out Chrome context", "chart_count": 5,
            "companies": list(prices), "selected_dates": initial_dates,
            "first_comparison_date": str(prices.index[0].date()),
            "last_comparison_date": str(prices.index[-1].date()),
            "closing_dates": len(prices), "daily_observations": len(expected_daily),
            "period_returns_percent": expected_period.to_dict(),
            "checks": ["CSV-based independent return calculations", "common 100 baseline",
                       "daily-return distributions", "independent Pearson correlations",
                       "all five charts respond to company filter", "all five charts respond to date filter",
                       "findings update", "empty selection handled", "no JavaScript or app errors"],
            "findings": initial_findings,
            "screenshots": [path.name for path in sorted(directory.glob("*.png"))],
        }
        (directory / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        browser.close()
        return report


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--output", type=Path, default=Path("test-results/browser"))
    args = parser.parse_args()
    report = verify(args.url, args.output)
    print(json.dumps(report, indent=2))

