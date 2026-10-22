import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Support & Resistance (AB Formula)", layout="wide")

# Force light look (also set in .streamlit/config.toml)
st.markdown(
    """
    <style>
    .stApp, [data-testid="stSidebar"] { background-color: #ffffff; color: #111111; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📈 Support & Resistance – AB Formula")
st.caption(
    "Levels are set on the 1st trading day of every month from the previous "
    "month's closing price. Pick any month to see its levels on the daily chart."
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
    years_history = st.slider("Years of history to load", 1, 15, 5)
    context_months = st.slider(
        "Months shown before the selected month", 0, 12, 2,
        help="Extra candles shown to the left of the selected month for context.",
    )
    pi_value = st.number_input(
        "First divisor", min_value=0.01, value=3.14, step=0.01, format="%.2f",
        help="Previous month close is first divided by this (default 3.14).",
    )
    divisor = st.number_input(
        "Second divisor", min_value=1.0, value=10.0, step=1.0,
        help="The result is then divided by this (default 10).",
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
    last_day = df.index.to_series().groupby(month).max()

    out = pd.DataFrame({"start": first_day, "end": last_day})
    out["prev_close"] = month_close.shift(1)
    out = out.dropna(subset=["prev_close"])
    out["pie"] = out["prev_close"] / pi_value / divisor
    for i in (1, 2, 3):
        out[f"R{i}"] = out["prev_close"] + i * out["pie"]
        out[f"S{i}"] = out["prev_close"] - i * out["pie"]
    return out


if not symbol:
    st.stop()

today = dt.date.today()
start = (pd.Timestamp(today) - pd.DateOffset(years=years_history)).date()
data = load_data(symbol, start)

if data.empty:
    st.error(f"No data found for '{symbol}'. Check the Yahoo Finance symbol.")
    st.stop()

levels = compute_monthly_levels(data, pi_value, divisor)
if levels.empty:
    st.warning("Not enough history to compute levels.")
    st.stop()

# ---------------------------------------------------------------- month picker
month_labels = [p.strftime("%B %Y") for p in levels.index]  # oldest -> newest
with st.sidebar:
    selected_label = st.selectbox(
        "Select month",
        options=month_labels[::-1],  # newest first
        index=0,
        help="Horizontal lines on the chart are drawn for this month.",
    )
sel_period = levels.index[month_labels.index(selected_label)]
sel = levels.loc[sel_period]

# chart window: context months before the selected month start, up to its end
# (or the latest available bar if the selected month is the current one)
win_start = sel["start"] - pd.DateOffset(months=context_months)
win_end = sel["end"]
view = data[(data.index >= win_start) & (data.index <= win_end)]

# ---------------------------------------------------------------- chart
fig = go.Figure()
has_ohlc = {"Open", "High", "Low"}.issubset(view.columns) and view["High"].notna().any()
if has_ohlc:
    fig.add_trace(
        go.Candlestick(
            x=view.index, open=view["Open"], high=view["High"],
            low=view["Low"], close=view["Close"], name="Price",
            increasing_line_color="#2ca02c", decreasing_line_color="#d62728",
        )
    )
else:  # mutual funds usually only have NAV
    fig.add_trace(go.Scatter(x=view.index, y=view["Close"], name="Close", mode="lines"))

COLORS = {"R": "#d62728", "S": "#2ca02c"}
DASH = {1: "solid", 2: "dash", 3: "dot"}
x0, x1 = view.index.min(), view.index.max()

# faint marker where the selected month begins
fig.add_vline(x=sel["start"], line_width=1, line_dash="dot", line_color="#888888")

for kind in ("R", "S"):
    for i in (1, 2, 3):
        name = f"{kind}{i}"
        y = sel[name]
        fig.add_shape(
            type="line", x0=x0, x1=x1, y0=y, y1=y,
            line=dict(color=COLORS[kind], width=1.6, dash=DASH[i]),
        )
        if show_labels:
            fig.add_annotation(
                x=x1, y=y, text=f"{name}: {y:,.2f}", showarrow=False,
                xanchor="left", font=dict(color=COLORS[kind], size=11),
            )
# previous close reference line
fig.add_shape(
    type="line", x0=x0, x1=x1, y0=sel["prev_close"], y1=sel["prev_close"],
    line=dict(color="#555555", width=1, dash="longdash"),
)
if show_labels:
    fig.add_annotation(
        x=x1, y=sel["prev_close"], text=f"Prev Close: {sel['prev_close']:,.2f}",
        showarrow=False, xanchor="left", font=dict(color="#555555", size=11),
    )

fig.update_layout(
    template="plotly_white",
    paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
    height=700, xaxis_rangeslider_visible=False,
    margin=dict(l=10, r=130, t=40, b=10), legend=dict(orientation="h"),
    title=f"{symbol} – Daily chart | Levels for {selected_label}",
)
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------- tables
last_price = view["Close"].iloc[-1]
st.subheader(f"Levels for {selected_label} (from {sel['start']:%d %b %Y})")
c1, c2, c3 = st.columns(3)
c1.metric("Previous month close", f"{sel['prev_close']:,.2f}")
c2.metric("Pie Factor", f"{sel['pie']:,.2f}")
c3.metric(f"Close on {view.index[-1]:%d %b %Y}", f"{last_price:,.2f}")

lv = pd.DataFrame(
    {
        "Level": ["R3", "R2", "R1", "Prev Close", "S1", "S2", "S3"],
        "Price": [sel["R3"], sel["R2"], sel["R1"], sel["prev_close"],
                  sel["S1"], sel["S2"], sel["S3"]],
    }
)
lv["Distance from last price %"] = (lv["Price"] / last_price - 1) * 100
st.dataframe(
    lv.style.format({"Price": "{:,.2f}", "Distance from last price %": "{:+.2f}%"}),
    hide_index=True, use_container_width=True,
)

with st.expander("Monthly level history"):
    hist = levels.drop(columns=["end"]).copy()
    hist.index = hist.index.strftime("%b %Y")
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
