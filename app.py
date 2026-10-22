import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Support & Resistance (AB Formula)", layout="wide")
st.title("📈 Support & Resistance – AB Formula")
st.caption(
    "Levels are reset on the 1st trading day of every month using the previous "
    "month's closing price."
)

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Inputs")
    symbol = st.text_input(
        "Yahoo Finance symbol",
        value="^NSEI",
        help="Examples: RELIANCE.NS, TCS.NS, ^NSEI (Nifty 50), ^NSEBANK, "
        "^BSESN, AAPL. For Indian mutual funds use the Yahoo code, e.g. 0P0000XVAA.BO",
    ).strip()
    months_back = st.slider("Months of history to chart", 2, 36, 6)
    pi_value = st.number_input(
        "First divisor", min_value=0.01, value=3.14, step=0.01, format="%.2f",
        help="Previous month close is first divided by this (default 3.14).",
    )
    divisor = st.number_input(
        "Second divisor", min_value=1.0, value=10.0, step=1.0,
        help="The result is then divided by this (default 10).",
    )
    show_all_months = st.checkbox(
        "Draw levels for every month in range (otherwise current month only)",
        value=True,
    )
    show_labels = st.checkbox("Show level labels", value=True)


# ---------------------------------------------------------------- data
@st.cache_data(ttl=3600, show_spinner="Downloading price data…")
def load_data(sym: str, start: dt.date) -> pd.DataFrame:
    df = yf.download(sym, start=start, auto_adjust=False, progress=False)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Close"])
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


def compute_monthly_levels(df: pd.DataFrame, pi_value: float, divisor: float) -> pd.DataFrame:
    """One row per month: prev close, pie factor, R1-R3, S1-S3,
    effective from that month's first trading day."""
    month = df.index.to_period("M")
    month_close = df["Close"].groupby(month).last()
    first_day = df.index.to_series().groupby(month).min()

    out = pd.DataFrame({"start": first_day})
    out["prev_close"] = month_close.shift(1)
    out = out.dropna(subset=["prev_close"])
    out["pie"] = out["prev_close"] / pi_value / divisor
    for i in (1, 2, 3):
        out[f"R{i}"] = out["prev_close"] + i * out["pie"]
        out[f"S{i}"] = out["prev_close"] - i * out["pie"]
    # month ends the day before next month starts (last month runs to last bar)
    out["end"] = out["start"].shift(-1)
    out.loc[out.index[-1], "end"] = df.index.max()
    return out


if not symbol:
    st.stop()

today = dt.date.today()
start = (pd.Timestamp(today) - pd.DateOffset(months=months_back + 2)).date()
data = load_data(symbol, start)

if data.empty:
    st.error(f"No data found for '{symbol}'. Check the Yahoo Finance symbol.")
    st.stop()

levels = compute_monthly_levels(data, pi_value, divisor)
chart_start = pd.Timestamp(today) - pd.DateOffset(months=months_back)
view = data[data.index >= chart_start]
levels_view = levels[levels["end"] >= chart_start]
if not show_all_months:
    levels_view = levels_view.tail(1)

if levels_view.empty:
    st.warning("Not enough history to compute levels.")
    st.stop()

# ---------------------------------------------------------------- chart
fig = go.Figure()
has_ohlc = {"Open", "High", "Low"}.issubset(view.columns) and view["High"].notna().any()
if has_ohlc:
    fig.add_trace(
        go.Candlestick(
            x=view.index, open=view["Open"], high=view["High"],
            low=view["Low"], close=view["Close"], name="Price",
        )
    )
else:  # mutual funds usually only have NAV
    fig.add_trace(go.Scatter(x=view.index, y=view["Close"], name="Close", mode="lines"))

COLORS = {"R": "#d62728", "S": "#2ca02c"}
DASH = {1: "solid", 2: "dash", 3: "dot"}
last_row = levels_view.index[-1]

for idx, row in levels_view.iterrows():
    x0 = max(row["start"], view.index.min())
    x1 = row["end"]
    for kind in ("R", "S"):
        for i in (1, 2, 3):
            name = f"{kind}{i}"
            y = row[name]
            fig.add_shape(
                type="line", x0=x0, x1=x1, y0=y, y1=y,
                line=dict(color=COLORS[kind], width=1.5, dash=DASH[i]),
            )
            if show_labels and idx == last_row:
                fig.add_annotation(
                    x=x1, y=y, text=f"{name}: {y:,.2f}", showarrow=False,
                    xanchor="left", font=dict(color=COLORS[kind], size=11),
                )

fig.update_layout(
    height=700, xaxis_rangeslider_visible=False,
    margin=dict(l=10, r=110, t=30, b=10), legend=dict(orientation="h"),
    title=f"{symbol} – Daily chart with monthly S/R levels",
)
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------- tables
cur = levels.iloc[-1]
st.subheader(f"Current month levels (from {cur['start']:%d %b %Y})")
c1, c2, c3 = st.columns(3)
c1.metric("Previous month close", f"{cur['prev_close']:,.2f}")
c2.metric("Pie Factor", f"{cur['pie']:,.2f}")
c3.metric("Last price", f"{data['Close'].iloc[-1]:,.2f}")

lv = pd.DataFrame(
    {
        "Level": ["R3", "R2", "R1", "Prev Close", "S1", "S2", "S3"],
        "Price": [cur["R3"], cur["R2"], cur["R1"], cur["prev_close"],
                  cur["S1"], cur["S2"], cur["S3"]],
    }
)
lv["Distance from last price %"] = (lv["Price"] / data["Close"].iloc[-1] - 1) * 100
st.dataframe(
    lv.style.format({"Price": "{:,.2f}", "Distance from last price %": "{:+.2f}%"}),
    hide_index=True, use_container_width=True,
)

with st.expander("Monthly level history"):
    hist = levels.drop(columns=["end"]).copy()
    hist["start"] = hist["start"].dt.date
    st.dataframe(hist.round(2).iloc[::-1], use_container_width=True)

with st.expander("Formula"):
    st.markdown(
        """
**On the 1st trading day of each month**

- Pie Factor = (Previous month close ÷ 3.14) ÷ 10
- R1 = Close + 1 × Pie, R2 = Close + 2 × Pie, R3 = Close + 3 × Pie
- S1 = Close − 1 × Pie, S2 = Close − 2 × Pie, S3 = Close − 3 × Pie

Levels stay fixed for the whole month.
"""
    )
st.caption("For educational purposes only. Not investment advice.")
