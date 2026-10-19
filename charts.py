"""Five Plotly comparisons using the same filtered data and company colors."""

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analytics import histogram_bins
from market_data import COLORS, COMPANIES


def label(symbol):
    return f"{COMPANIES[symbol]} ({symbol})"


def style(fig, title, height=370):
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color="#122744")),
        template="plotly_white", height=height,
        font=dict(family="Arial, sans-serif", size=12, color="#334155"),
        margin=dict(l=55, r=30, t=70, b=65),
        legend=dict(orientation="h", y=-0.23, x=0),
        paper_bgcolor="white", plot_bgcolor="white",
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="#eef2f6", zeroline=False)
    return fig


def performance_chart(data):
    fig = go.Figure()
    for symbol in data.indexed:
        fig.add_trace(go.Scatter(
            x=data.indexed.index.tolist(), y=data.indexed[symbol].tolist(),
            mode="lines", name=label(symbol), line=dict(color=COLORS[symbol], width=2.6),
            hovertemplate="%{x|%b %d, %Y}<br>Index: %{y:.2f}<extra>%{fullData.name}</extra>",
        ))
    fig.add_hline(y=100, line_dash="dot", line_color="#94a3b8")
    style(fig, "1. Indexed stock performance", 400)
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(title="Trading date")
    fig.update_yaxes(title="Adjusted performance index (start = 100)")
    return fig


def return_chart(data):
    symbols = list(data.period_returns.index)
    values = data.period_returns.tolist()
    fig = go.Figure(go.Bar(
        x=[label(symbol) for symbol in symbols], y=values,
        marker_color=[COLORS[symbol] for symbol in symbols],
        text=[f"{value:+.2f}%" for value in values], textposition="outside", cliponaxis=False,
        hovertemplate="%{x}<br>Adjusted return: %{y:.2f}%<extra></extra>",
    ))
    style(fig, "2. Return over the selected period")
    low, high = min(0, min(values)), max(0, max(values))
    padding = max((high - low) * 0.2, 1)
    fig.update_yaxes(title="Adjusted period return (%)", range=[low - padding, high + padding])
    fig.update_xaxes(title="Company")
    fig.add_hline(y=0, line_color="#94a3b8", line_width=1)
    return fig


def histogram_chart(data):
    symbols = list(data.daily_returns.columns)
    edges = histogram_bins(data.daily_returns)
    fig = make_subplots(rows=1, cols=len(symbols), shared_yaxes=True,
                        subplot_titles=[label(symbol) for symbol in symbols], horizontal_spacing=0.08)
    max_percent = 0
    for i, symbol in enumerate(symbols, 1):
        values = data.daily_returns[symbol].to_numpy()
        counts, _ = np.histogram(values, bins=edges)
        max_percent = max(max_percent, (counts / len(values) * 100).max())
        fig.add_trace(go.Histogram(
            x=values.tolist(), xbins=dict(start=edges[0], end=edges[-1], size=edges[1] - edges[0]),
            histnorm="percent", name=label(symbol), marker_color=COLORS[symbol], showlegend=False,
            hovertemplate="Daily return: %{x:.2f}%<br>Trading days: %{y:.1f}%<extra>%{fullData.name}</extra>",
        ), row=1, col=i)
    style(fig, "4. Distribution of daily returns", 380)
    fig.update_layout(bargap=0.05)
    fig.update_annotations(font_size=12)
    fig.update_xaxes(title="Daily return (%)", range=[edges[0], edges[-1]])
    fig.update_yaxes(range=[0, max_percent * 1.15], ticksuffix="%")
    fig.update_yaxes(title="Trading days (%)", row=1, col=1)
    return fig


def box_chart(data):
    fig = go.Figure()
    for symbol in data.daily_returns:
        fig.add_trace(go.Box(
            y=data.daily_returns[symbol].tolist(), name=label(symbol),
            marker_color=COLORS[symbol], boxpoints="outliers", showlegend=False,
            hovertemplate="Daily return: %{y:.2f}%<extra>%{fullData.name}</extra>",
        ))
    style(fig, "3. Daily-return spread and outliers")
    fig.update_yaxes(title="Daily adjusted return (%)")
    fig.update_xaxes(title="Company")
    fig.add_hline(y=0, line_color="#94a3b8", line_width=1, line_dash="dot")
    return fig


def correlation_chart(data):
    corr = data.correlations
    names = [label(symbol) for symbol in corr.columns]
    text = [[f"{value:.2f}" if np.isfinite(value) else "N/A" for value in row]
            for row in corr.to_numpy()]
    fig = go.Figure(go.Heatmap(
        z=corr.to_numpy().tolist(), x=names, y=names, zmin=-1, zmax=1, zmid=0,
        colorscale=[[0, "#e9a7a4"], [0.5, "#f8fafc"], [1, "#87afd9"]],
        text=text, texttemplate="%{text}", textfont=dict(size=17, color="#122744"),
        colorbar=dict(title="Pearson r", tickvals=[-1, -0.5, 0, 0.5, 1]),
        hovertemplate="%{x}<br>%{y}<br>Pearson r: %{z:.3f}<extra></extra>",
        hoverongaps=False,
    ))
    style(fig, "5. Correlation of daily returns", 390)
    fig.update_xaxes(title="Company", side="bottom")
    fig.update_yaxes(title="Company", autorange="reversed")
    return fig
